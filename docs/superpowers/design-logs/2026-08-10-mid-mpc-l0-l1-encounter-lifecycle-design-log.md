# 设计日志: Mid-MPC L0/L1 Encounter Lifecycle 深化

> **模式**: 重构        **创建**: 2026-08-10
> **关联 spec**: `docs/superpowers/specs/2026-08-11-mid-mpc-l0-l1-encounter-lifecycle-solution-pack.md`
> **状态**: Step6完成，已交付to-spec（2026-08-11）

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|----|------|------|---------|------|------|
| DP-01 | Encounter Lifecycle module 的责任范围；哪些复杂度必须从 _MidMpcFacade 移入，哪些仍归 Problem Assembler、IPOPT core、L4 | 架构 | — | Step4 已确认 | Step2 DP-01 / Step4 DP-01 |
| DP-02 | 态势分类的权威来源：继续直接复用 evaluator classify_geometry，还是提升为 planner-neutral interface | 接口 | — | Step4 已确认 | Step2 DP-02 / Step4 DP-02 |
| DP-03 | 是否采用显式、逐目标、有记忆的 COLREG encounter lifecycle 技术，以及状态表达方式 | 技术 | TD-01 | Step4 已确认 | Step2 DP-03 / Step4 DP-03 |
| DP-04 | Pairwise observation contract：位置/速度/航向、船体尺度、DCPA/TCPA、相对方位、质量与时间戳 | 接口 | TD-01 | Step4 已确认 | Step2 DP-04 / Step4 DP-04 |
| DP-05 | OT/HO/CS/overtaken/clear 的几何分类与 give-way/stand-on 角色映射 | 算法 | TD-01 | Step4 已确认 | Step2 DP-05 / Step4 DP-05 |
| DP-06 | 风险阶段与进入条件：何时从 clear/monitor 进入 committed，是否基于 range、DCPA、TCPA、horizon、趋势 | 约束 | TD-01 | Step4 已确认 | Step2 DP-06 / Step4 DP-06 |
| DP-07 | Lock-on 与 hysteresis：如何抑制因本船改向、测量噪声引起的 encounter flicker | 算法 | TD-01 | Step4 已确认 | Step2 DP-07 / Step4 DP-07 |
| DP-08 | 行为意图：GIVE_WAY/HOLD、starboard/port、minimum action、固定 course reference 的所有权 | 算法 | TD-01 | Step4 已确认 | Step2 DP-08 / Step4 DP-08 |
| DP-09 | Rule 17 stand-on 到 emergency action 的升级语义与触发条件 | 算法 | TD-01 | Step4 已确认 | Step2 DP-09 / Step4 DP-09 |
| DP-10 | Release：CPA 通过、past-and-clear、距离回升、航线回归之间的关系 | 算法 | TD-01 | Step4 已确认 | Step2 DP-10 / Step4 DP-10 |
| DP-11 | Rearm：同一目标释放后是否允许重入；track 丢失、ID 复用、目标重新构成风险时如何处理 | 算法 | TD-01 | Step4 已确认 | Step2 DP-11 / Step4 DP-11 |
| DP-12 | 多目标 aggregation：相冲突规则、动作侧、风险排序、最多 16 目标及 primary target 的语义 | 算法 | TD-01 | Step4 已确认 | Step2 DP-12 / Step4 DP-12 |
| DP-13 | Degraded/unknown observation：数据陈旧、非有限值、低置信、目标消失时保持、降级或 fail-stop | 约束 | TD-01 | Step4 已确认 | Step2 DP-13 / Step4 DP-13 |
| DP-14 | 向 L1 Problem Assembler 交付的 immutable decision facts、物理时间语义与 reset/evidence contract | 接口 | TD-01 | Step4 已确认 | Step2 DP-14 / Step4 DP-14 |
| DP-15 | 生命周期可观测性：transition reason、触发证据、commit course、release/rearm、multi-target 冲突如何进入 PlannerTrace | 接口 | TD-01 | Step4 已确认 | Step2 DP-15 / Step4 DP-15 |
| DP-16 | L0/L1 验收矩阵：OT/HO/CS、stand-on/overtaken、多目标、flicker、track-loss 的 contract tests | 约束 | — | Step4 已确认 | Step2 DP-16 / Step4 DP-16 |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|----|------|------------------|----------|
| TD-01 | Stateful COLREG Encounter Lifecycle | observation contract(DP-04) → classification/role(DP-05) → risk entry(DP-06) → lock/hysteresis(DP-07) → intent(DP-08) → stand-on escalation(DP-09) → release(DP-10) → rearm/track identity(DP-11) → multi-target aggregation(DP-12) → degraded input(DP-13) → planner handoff(DP-14) → transition evidence(DP-15) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|----|------|-----------|--------|----------|
| BL-01 | classify_geometry 属 evaluator；直接作为运行时决策权威是否形成自评耦合 | DP-02 | 高 | 证据闭环 |
| BL-02 | 当前固定 `commit_course + 5°` 已被否决；需确定满足 early and substantial、单次可辨识动作的独立 ODD 最小改向语义与参数 | DP-08 | 高 | 证据闭环(含UNKNOWN) |
| BL-03 | overtaking “past-and-clear” 的充分条件；仅投影超越 + 距离 190m 是否会过早释放 | DP-10 | 高 | 证据闭环(含UNKNOWN) |
| BL-04 | crossing stand-on 何时可依 Rule 17 主动动作；当前 horizon 内选中目标但 intent 仍 HOLD 的业务语义 | DP-09 | 高 | 证据闭环 |
| BL-05 | 同一目标 release 后永久禁止重入，遇到复合/二次风险是否安全 | DP-11 | 高 | 证据闭环(含UNKNOWN) |
| BL-06 | 多目标中 mandatory starboard 与 overtaking side 冲突时，pairwise 合规能否推出 aggregate 合规 | DP-12 | 高 | 证据闭环(含UNKNOWN) |
| BL-07 | risk entry 应使用 evaluator stage profile 还是 Mid-MPC 独立 ODD 参数；避免测试定义反向控制 planner | DP-06 | 高 | 证据闭环 |
| BL-08 | Track ID 稳定性、丢失超时、ID 复用保证目前未在 PlannerInput contract 中显式给出 | DP-11/DP-13 | 中 | 证据闭环(含UNKNOWN) |
| BL-09 | NLM 快调受本机 SOCKS socksio 缺失阻塞；外部证据当前来自一手论文与 IMO | DP-03 | 中 | 证据闭环(调研路径替代) |
| BL-10 | Rule 13 未规定追越侧；已否决 starboard-only，OT side 应按相对态势在 commit 时确定，具体选择函数待裁决 | DP-08 | 高 | 证据闭环 |
| BL-11 | Rule 16 的 early and substantial action 如何映射为可观测进入时机与最小动作；当前 one-shot + 固定 5° 是否充分 | DP-06/DP-08 | 高 | 证据闭环(含UNKNOWN) |
| BL-12 | Planner 的 encounter 分类角度、risk distance 与进入阈值应由哪个独立 ODD/profile 提供，且不能由 evaluator profile 反向控制 | DP-02/DP-05/DP-06 | 高 | 证据闭环(含UNKNOWN) |
| BL-13 | Planner lifecycle 的最小状态集合与正交分解；MONITOR/ACTING/EMERGENCY/PAST_CLEAR/DEGRADED 哪些必须显式 | DP-03 | 高 | 证据闭环(含UNKNOWN) |
| BL-14 | 上游没有显式 track association generation；target_id 复用时，新目标可能继承旧 lifecycle state | DP-04/DP-11 | 高 | 证据闭环(含UNKNOWN) |
| BL-15 | 目标 COG 最低有效速度、协方差质量阈值及 degraded observation 的判定来源尚未确定 | DP-04/DP-13 | 高 | 证据闭环(含UNKNOWN) |
| BL-16 | HO/CS/OT 分类角度边界、速度差容差需由独立 Planner ODD profile 定义 | DP-05 | 高 | 证据闭环(含UNKNOWN) |
| BL-17 | 低速、近共速及恰落分类边界时，应输出 UNDETERMINED 还是保持已锁定标签 | DP-05/DP-07 | 高 | 证据闭环(含UNKNOWN) |
| BL-18 | `action_lead_time_s`、船体净空进入值与 urgent 距离缺乏独立 Planner ODD 标定 | DP-06 | 高 | 证据闭环(含UNKNOWN) |
| BL-19 | 风险进入使用瞬时匀速 CPA，还是需要 nominal-route prediction | DP-06 | 高 | 证据闭环(含UNKNOWN) |
| BL-20 | Rule 13 duty 与风险门槛关系；预测侧向净空充分时是否仍需强制改向 | DP-06/DP-08 | 高 | 证据闭环(含UNKNOWN) |
| BL-21 | `entry_confirm_s` 数值及 urgent candidate 绕过确认的条件 | DP-07 | 高 | 证据闭环(含UNKNOWN) |
| BL-22 | 目标船真实大幅机动后，哪些 locked facts 仍不可变，哪些需要受控重判 | DP-07/DP-11 | 高 | 证据闭环(含UNKNOWN) |
| BL-23 | HO/CS/OT 分类边界往返但 ownship role 相同时，候选确认是否允许按角色合并 | DP-07 | 中 | 证据闭环(含UNKNOWN) |
| BL-24 | substantial course angle 精确值、动力学可达时间及物理时间内可辨识性 | DP-08 | 高 | 证据闭环(含UNKNOWN) |
| BL-25 | OT 如何同时证明选定 passing side 与实际通过侧，而非仅证明初始转向符号 | DP-08/DP-15/DP-16 | 高 | 证据闭环(含UNKNOWN) |
| BL-26 | 首次 substantial action 不足时，允许何种离散、可审计的 commitment revision | DP-08 | 高 | 证据闭环(含UNKNOWN) |
| BL-27 | 如何从目标动作趋势、风险改善与持续时间定义 Rule 17 的 appropriate action | DP-09 | 高 | 证据闭环(含UNKNOWN) |
| BL-28 | `latest_expected_action_s`、MAY_ACT 与 MUST_ACT 的物理时间/净空阈值 | DP-09 | 高 | 证据闭环(含UNKNOWN) |
| BL-29 | 如何近似判断“give-way vessel 单独行动已无法避免碰撞” | DP-09 | 高 | 证据闭环(含UNKNOWN) |
| BL-30 | Rule 17(c) 的 port-alteration restriction 在多目标动作冲突下的优先级 | DP-09/DP-12 | 高 | 证据闭环(含UNKNOWN) |
| BL-31 | footprint-aware release clearance、超前净空与 `release_confirm_s` 的 ODD 参数 | DP-10 | 高 | 证据闭环(含UNKNOWN) |
| BL-32 | PAST_CLEAR 到 LOS recovery 的交付及恢复中重新形成风险的检测 | DP-10/DP-11 | 高 | 证据闭环(含UNKNOWN) |
| BL-33 | 目标突发转向时，future-clearance guard horizon 多长才足够 | DP-10 | 高 | 证据闭环(含UNKNOWN) |
| BL-34 | Ship 已提供 `T_chi/T_U/r_max`，但 PlannerInput 未保留；maneuverability facts contract 需补齐 | DP-04/DP-10/DP-14 | 高 | 证据闭环(含UNKNOWN) |
| BL-35 | track generation 的上游提供方式及旧 tracker 的降级语义 | DP-04/DP-11 | 高 | 证据闭环(含UNKNOWN) |
| BL-36 | coast timeout、reacquisition window、released tombstone TTL | DP-11 | 高 | 证据闭环(含UNKNOWN) |
| BL-37 | identity discontinuity 的位置/速度/时间门槛 | DP-11/DP-13 | 高 | 证据闭环(含UNKNOWN) |
| BL-38 | COASTING 状态继续原 commitment，还是按 observation health 进入保守动作 | DP-11/DP-13 | 高 | 证据闭环(含UNKNOWN) |
| BL-39 | mandatory rule constraints、conditional restrictions 与 side preferences 的正式优先矩阵 | DP-12 | 高 | 证据闭环(含UNKNOWN) |
| BL-40 | active targets 超过 16 时 `CAPACITY_EXCEEDED` 的 no-fallback 执行语义 | DP-12/DP-14 | 高 | 证据闭环(含UNKNOWN) |
| BL-41 | course conflict 下显著减速/停车 commitment 的进入与解除 | DP-12 | 高 | 证据闭环(含UNKNOWN) |
| BL-42 | primary target 切换 hysteresis，不得扰动其他 target lifecycle | DP-12/DP-15 | 中 | 证据闭环(含UNKNOWN) |
| BL-43 | covariance 到安全裕度的映射与 sigma confidence level | DP-13 | 高 | 证据闭环(含UNKNOWN) |
| BL-44 | UNUSABLE observation 后 no-fallback runtime 行为及控制权归属 | DP-13/DP-14 | 高 | 证据闭环(含UNKNOWN) |
| BL-45 | COASTING motion model 与 uncertainty 随 age 增长的模型 | DP-11/DP-13 | 高 | 证据闭环(含UNKNOWN) |
| BL-46 | 低速 UNKNOWN_ROLE target 如何参与 multi-target capacity 与 risk ordering | DP-12/DP-13 | 中 | 证据闭环(含UNKNOWN) |
| BL-47 | cycle identity 与 input hash 的生成位置及 retry 幂等权威 | DP-14 | 高 | 证据闭环(含UNKNOWN) |
| BL-48 | session epoch、reset trigger 与 reset reason 的上游权威 | DP-14 | 高 | 证据闭环(含UNKNOWN) |
| BL-49 | time gap 多大应拒绝 cycle，而非正常推进 lifecycle timers | DP-14 | 高 | 证据闭环(含UNKNOWN) |
| BL-50 | decision snapshot schema version 与 PlannerTrace JSON 映射 | DP-14/DP-15 | 中 | 证据闭环(含UNKNOWN) |
| BL-51 | typed lifecycle evidence schema 的兼容版本策略 | DP-15 | 中 | 证据闭环(含UNKNOWN) |
| BL-52 | bounded ring buffer 容量与长期 event sink 所有权 | DP-15 | 中 | 证据闭环(含UNKNOWN) |
| BL-53 | Planner ODD profile/config hash 的稳定生成与 trace provenance | DP-15 | 中 | 证据闭环(含UNKNOWN) |
| BL-54 | GUI 默认展示哪些 lifecycle facts，避免隐藏关键证据或信息过载 | DP-15/DP-16 | 中 | 证据闭环(含UNKNOWN) |
| BL-55 | 非合作 give-way target 驱动 stand-on Rule 17 escalation 的确定性 fixture | DP-09/DP-16 | 高 | 证据闭环(含UNKNOWN) |
| BL-56 | substantial action 的实际 trajectory 判据，不能只检查 commitment trace | DP-08/DP-16 | 高 | 证据闭环(含UNKNOWN) |
| BL-57 | dynamic release/domain threshold 与现有 evaluator 50m hard gate 的双重证据 | DP-10/DP-16 | 高 | 证据闭环(含UNKNOWN) |
| BL-58 | OT port/starboard 镜像场景与 multi-target maneuver-conflict fixtures | DP-08/DP-12/DP-16 | 高 | 证据闭环(含UNKNOWN) |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|----|----------|------|----------|----------|----------|------|
| [R1] | PROJECT_FACT | 当前 Colav _MidMpcFacade、classify_geometry、PairwiseColregFSM、CustomMPCAdapter | 高 | 高 | 高 | DP-01..DP-15 |
| [R2] | PROJECT_FACT | Mid-MPC integration/single-encounter/multiship tests 与 capability evidence | 高 | 高 | 高 | DP-06..DP-16 |
| [R3] | DOCUMENTED_INTENT | M5_MPC_业务流程分层架构.md 的 L0、L1.6、L4.3、LX | 高 | 中 | 高 | DP-01..DP-16 |
| [R4] | PROJECT_FACT | GitLab l3-tdl@bf5de9e0 的 pure input/decision seams | 高 | 高 | 中 | DP-01/DP-14/DP-15 |
| [R5] | DOMAIN_EVIDENCE | Eriksen et al. 2020：三层 COLAV 与基于 geometry、CPA distance/time 的 COLREG state machine | 高 | 高 | 高 | DP-03..DP-12 |
| [R6] | DOMAIN_EVIDENCE | IMO COLREG 官方说明：Rules 8、13、14、15、16、17 角色与动作责任 | 高 | 高 | 高 | DP-05/DP-08/DP-09/DP-10 |
| [R7] | DOMAIN_EVIDENCE | He et al. 2025：16-category encounter classification 与逐预测步安全距离 | 中 | 高 | 中 | DP-05/DP-06/DP-12 |
| [R8] | DOMAIN_EVIDENCE | USCG Navigation Rules：Rule 13/14/16/17 的正式规则文本 | 高 | 高 | 高 | DP-05/DP-08/DP-09/DP-10 |
| [R9] | DOMAIN_EVIDENCE | Hansen et al. 2020：逐船有限状态自动机、理解与预判分离、多船协调 | 高 | 高 | 高 | DP-03/DP-05/DP-06/DP-12 |
| [R10] | DOMAIN_EVIDENCE | Bergman et al. 2020：离散 COLREG 状态在连续优化期间保持固定 | 高 | 高 | 高 | DP-03/DP-07/DP-14 |
| [R11] | PROJECT_FACT | GitLab l3-tdl@4c8ff3bd 的 pure activation FSM 与非对称进入/恢复 hysteresis | 高 | 高 | 中 | DP-01/DP-06/DP-07/DP-14 |
| [R12] | DOMAIN_EVIDENCE | Du et al. 2021：empirical ship domain 随船舶尺度、速度、COLREG role 与避让动作变化 | 高 | 高 | 高 | DP-06/DP-10 |
| [R13] | DOMAIN_EVIDENCE | IMO MSC.137(76)：turning advance、tactical diameter、initial turn、stopping ability 的 length-normalized manoeuvrability criteria | 高 | 高 | 高 | DP-04/DP-10/DP-14 |
| [R14] | DOMAIN_EVIDENCE | USCG Navigation Rules Handbook 2024：Rules 7/8/13/14/16/17 的正式文本；定性 action、责任、疑义与 passing-side 语义 | 高 | 高 | 高 | DP-05..DP-10 |
| [R15] | DOMAIN_EVIDENCE | IMO MSC.192(79)：CPA/TCPA alarm limits 由 operator 按本船设定；trial manoeuvre 应含本船动态与可调 course/speed | 高 | 高 | 中 | DP-02/DP-06 |
| [R16] | DOMAIN_EVIDENCE | IMO A.601(15)：船上应提供 turning、course-change、stopping time/track-reach 与 loading/environment 影响信息 | 高 | 高 | 中高 | DP-04/DP-06/DP-10 |
| [R17] | DOMAIN_EVIDENCE | Hagen et al. 2024 AIS 实证：动作时机/幅度/OT side 分布依 encounter 与水域变化；作者不推荐通用单值 | 高 | 高 | 中 | DP-05/DP-06/DP-08 |
| [R18] | DOMAIN_EVIDENCE | Bąk et al. 2021：实船 action point 与 relative speed、target length、open/restricted water 相关 | 高 | 中高 | 低 | DP-06 |
| [R19] | DOMAIN_EVIDENCE | Ha et al. 2021：CPA+ship-domain 风险显式依 DCPA/TCPA、双方长度、relative speed；标定范围有限 | 高 | 中高 | 中低 | DP-04/DP-06/DP-10 |
| [R20] | DOMAIN_EVIDENCE | Tengesdal et al. 2020：CVM/straight-line CPA 在预计目标机动时受限；scenario MPC 仍有 open-loop/CV 假设 | 高 | 中高 | 中 | DP-06 |
| [R21] | DOMAIN_EVIDENCE | Woerner et al. 2019：COLREG protocol evaluation/certification 与 planner decision 属不同职责 | 高 | 高 | 中高 | DP-01/DP-02 |
| [R22] | PROJECT_FACT | MASS M6 current source：phase FSM 与 OnsetSnapshot/Role/EncounterType/TimingPhase 正交 facts，ACTIVE 保持 onset classification | 高 | 高 | 高 | DP-03/DP-07/DP-14 |
| [R23] | DOMAIN_EVIDENCE | Hansen et al. 2024 stochastic COLREG classification：边界不确定性可使 deterministic label 翻转，概率阈值仍 implementation-specific | 高 | 中 | 中 | DP-04/DP-05/DP-07 |
| [R24] | DOMAIN_EVIDENCE | Otal Investments v. M/V Clary 2007：OT safe execution 依环境、速度、间距与船舶能力，不产生固定 passing side/距离 | 中高 | 高 | 中 | DP-06/DP-08/DP-10 |
| [R25] | DOMAIN_EVIDENCE | Wang 2013 dynamic quaternion ship domain：非对称 domain 显式依船长、速度、advance、tactical diameter 与操纵模型 | 高 | 高 | 中 | DP-06/DP-10 |
| [R26] | DOMAIN_EVIDENCE | Johansen et al. 2016：mission path 与 collision avoidance 分层；receding horizon 持续更新并在 hazard 后恢复 nominal route | 高 | 高 | 高 | DP-10/DP-11 |
| [R27] | DOMAIN_EVIDENCE | The Dream Star [2017] SGHC 220：Rule17(a)(ii)/(b) 是 stand-on 义务的不同 exceptional triggers | 高 | 高 | 中高 | DP-09 |
| [R28] | DOMAIN_EVIDENCE | MAIB Scottish Viking/Homeland 2011：迟到、轻微且依赖双方动作的 give-way maneuver 不满足 Rules 8/16 | 高 | 高 | 中 | DP-08/DP-09 |
| [R29] | DOMAIN_EVIDENCE | Du et al. 2020：用 turning-point、maneuverability reachable velocity 与 NL-VO 评估 target action adequacy | 高 | 高 | 中 | DP-09 |
| [R30] | DOMAIN_EVIDENCE | Zaccone et al. 2021：以计划路径交点顺序/几何验证 crossing 与 overtaking passing behavior，而非首个 control sign | 高 | 中高 | 中高 | DP-08/DP-16 |
| [R31] | DOMAIN_EVIDENCE | He et al. 2021：多船规划要求同时避开所有 dangerous targets，候选相对速度不得落入任一 target VO | 高 | 中高 | 中 | DP-12/DP-16 |
| [R32] | DOMAIN_EVIDENCE | Sawada et al. 2021：22 个 Imazu complex scenarios 用于多船 conflict-resolution 验证 | 高 | 中高 | 中 | DP-12/DP-16 |
| [R33] | PROJECT_FACT | MASS risk model：primary target 使用 score-gap 或连续样本 hysteresis，且不重置 per-target risk facts | 高 | 高 | 中高 | DP-12/DP-15 |
| [R34] | PROJECT_FACT | 当前 tracker→PlannerInput 只交裸 ID/state/cov/hull；Mid 以 ID 直接持有/删除 commitment，缺 generation、lost/coast/reacquire 语义 | 高 | 高 | 高 | DP-04/DP-11/DP-13 |
| [R35] | DOMAIN_EVIDENCE | IMO MSC.192/MSC.112 区分 lost target、target swap、association 与 COG/SOG validity，但不提供统一 ID reuse、coast 或最低速度阈值 | 高 | 高 | 中 | DP-04/DP-11/DP-13 |
| [R36] | PROJECT_FACT | VIMMJIPDA 内部具新 track index、existence/missed-step/termination 与 covariance propagation，但公共 tracker contract 丢弃这些状态 | 高 | 中高 | 高 | DP-04/DP-11/DP-13 |
| [R37] | DOMAIN_EVIDENCE | Fossen & Fossen：低速时 course/heading 关系与 COG 可靠性存在可观测限制；试验速度不能提升为通用门槛 | 高 | 中高 | 中低 | DP-04/DP-13 |
| [R38] | DOMAIN_EVIDENCE | EUROCONTROL ASTERIX CAT062 显式表达 track status、coasting、time 与 position/velocity accuracy；identity/discontinuity 阈值由系统定义 | 高 | 高 | 中 | DP-11/DP-13 |
| [R39] | DOMAIN_EVIDENCE | NIST χ² confidence ellipse 与 chance-constrained collision avoidance 支持 covariance→probabilistic margin；confidence/risk budget 与非高斯处理仍需 ODD 决定 | 高 | 中高 | 中 | DP-13 |
| [R40] | PROJECT_FACT | Ship→PlannerInput 丢失 T_chi/T_U/r_max；UNUSABLE 与无目标同形；Adapter/Session 现有 identity/reset/gap/error 链没有 cycle hash、epoch 或 transaction | 高 | 高 | 高 | DP-04/DP-13/DP-14 |
| [R41] | DOMAIN_EVIDENCE | ROS 2 time 支持 forward/backward jump callback 与应用自定 threshold，不提供 Playground 通用 gap seconds | 高 | 高 | 中高 | DP-14 |
| [R42] | PROJECT_FACT | PlannerTrace 1.0、session events、GUI、profile/config hash 与 substantial-action tests 的当前 schema/retention/provenance/可见性边界 | 高 | 高 | 高 | DP-14/DP-15/DP-16 |
| [R43] | DOMAIN_EVIDENCE | CloudEvents/OpenTelemetry/SemVer 提供 event envelope、schema identity、additive/breaking 兼容与 exporter ownership 先例，不规定本项目字段和容量 | 高 | 高 | 中高 | DP-14/DP-15 |
| [R44] | DOMAIN_EVIDENCE | RFC 8785 定义可重复 JSON canonicalization，适合稳定 hash；当前 registry sorted JSON 且含绝对 dependency path，不是 JCS/跨 checkout 内容 identity | 高 | 高 | 高 | DP-15 |
| [R45] | PROJECT_FACT | 当前单遭遇测试只校验 command angle；multiship/evaluator 有实际 COG/CPA 轨迹指标，但 baseline/window 未绑定 lifecycle commit→past-clear | 高 | 高 | 高 | DP-08/DP-16 |
| [R46] | DOMAIN_EVIDENCE | OpenTelemetry Logs SDK 与 bounded deque 提供 processor/exporter、bounded queue 机制；实际容量/overflow/persistence policy 无外部通用值 | 高 | 高 | 中高 | DP-15 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|----|----------|-----------|-----------|
| SC-01 | HO：初始 give-way，改向后几何标签变化 | 应保持可观察的 starboard commitment，直至安全释放 | DP-05..DP-10 |
| SC-02 | OT：本船追越目标 | 按相对态势选择 port/starboard 通过侧、固定而不累加的 substantial commitment、past-and-clear、回归 | DP-05/DP-08/DP-10/DP-11 |
| SC-03 | CS give-way | 早期 starboard action、从目标船尾通过、避免策略 flicker | DP-05..DP-10 |
| SC-04 | CS stand-on | 初期 HOLD；对方不让路且风险升级时存在可审计 Rule 17 transition | DP-06/DP-09/DP-15 |
| SC-05 | Overtaken | HOLD 与安全升级不矛盾；不把自身误判为 overtaking | DP-05/DP-09 |
| SC-06 | 多目标同时触发不同 pairwise 规则 | aggregation 决定唯一可执行 intent；每目标证据仍可追踪 | DP-12/DP-15 |
| SC-07 | 同一目标标签在 clear/OT/clear 间抖动 | hysteresis 阻止周期性左/右切换 | DP-06/DP-07 |
| SC-08 | track 暂时丢失后恢复或 ID 复用 | 不静默遗忘危险 commitment，不把新目标继承旧状态 | DP-11/DP-13 |
| SC-09 | reset/回放/倒退时间 | 所有 per-target state、course、released 集合可确定清空 | DP-14/DP-16 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|----|----------|------|-----------|------|------|
| VR-01 | DP-01 Encounter Lifecycle 责任范围 | 采用纯 Python、stateful、solver-agnostic 深模块，唯一拥有 lifecycle state/aggregate/evidence；Assembler、IPOPT、Adapter、L4 保持独立 | 采纳(final) | 消除 facade 隐式多重责任及失败 mutation，同时保持 L0/L1/solver/runtime 验收边界 | 2026-08-11 |
| VR-02 | DP-02 分类权威 | 共享 planner-neutral physical geometry facts；Planner lifecycle 与 Evaluator 分别拥有自己的 classification/profile/FSM/verdict | 采纳(final) | 避免 evaluator 反控 planner，同时避免 CPA/坐标数学重复漂移 | 2026-08-11 |
| VR-03 | DP-03 Lifecycle 技术与状态表达 | 采用逐目标 deterministic pure FSM；以 lifecycle/encounter/role/Rule17/action/side/health/identity/evidence 正交 typed facts 表达 | 采纳(final) | 保持 solve-cycle duty 稳定，同时避免 monolithic enum 状态爆炸 | 2026-08-11 |
| VR-04 | DP-04 Pairwise observation contract | 采用 cycle-level ownship/header + per-target immutable observation；显式 generation/provenance/validity/geometry/maneuverability，未知不填假值 | 采纳(final) | 为 identity、degraded、dynamic margin、atomic replay 提供可复现事实边界 | 2026-08-11 |
| VR-05 | DP-05 几何分类与角色映射 | EncounterKind 与 OwnshipRole 正交；Rule13 112.5°为规则边界，其余容差归 Planner ODD；低速/边界输出 UNKNOWN，risk/action 后置 | 采纳(final) | 防止风险阈值改写规则事实，并保留 Rule13 doubt 与 ODD unsupported 证据 | 2026-08-11 |
| VR-06 | DP-06 风险阶段与进入条件 | 使用 role+approaching+physical TCPA+footprint/uncertainty-aware hull clearance 联合 candidate；独立 Planner ODD，CV-CPA 为显式 baseline | 采纳(final) | 避免 horizon/evaluator 耦合与单变量误判，同时保留 CV 失效边界 | 2026-08-11 |
| VR-07 | DP-07 Lock-on/hysteresis | 使用 physical-time confirmation、constraint-semantic candidate key 与 immutable commit lock；urgent显式绕过，revision离散可审计 | 采纳(final) | 抑制label flicker且不把调度频率、primary切换或instantaneous CLEAR变成业务状态 | 2026-08-11 |
| VR-08 | DP-08 Substantial commitment | baseline-relative immutable commitment；动态可达且明显的course/speed动作；minimum约束持续至实际达成；OT双侧评估后锁定 | 采纳(final) | 消除固定5°/累加小转向和OT机械右侧，并以实际轨迹证明动作 | 2026-08-11 |
| VR-09 | DP-09 Rule17 escalation | 显式 STAND_ON→MAY_ACT→MUST_ACT；appropriate action联合趋势/改善/持续/可达性；MUST使用target-alone reachable-set proxy并保留UNKNOWN | 采纳(final) | 对齐17(a)(i)/(a)(ii)/(b)不同强度，避免永久HOLD或纯TCPA升级 | 2026-08-11 |
| VR-10 | DP-10 Release/past-clear | COMMITTED→PAST_CLEAR→RELEASED；footprint/maneuverability-aware dynamic margin、持续分离、future guard与确认时间联合；恢复期继续监视 | 采纳(final) | 防止TCPA/190m单条件过早release，并分离COLREG duty与route recovery | 2026-08-11 |
| VR-11 | DP-11 Rearm/track identity | `(target_id,generation)`+episode；OBSERVED→COASTING→LOST；有限reacquisition/tombstone；release后可重新确认新episode | 采纳(final) | 避免一帧丢失消除duty、ID reuse继承旧动作和永久release屏蔽二次风险 | 2026-08-11 |
| VR-12 | DP-12 多目标aggregation | 全目标lifecycle后聚合约束，再由L1选≤16；显式priority/conflict/capacity；primary仅解释，不重置状态 | 采纳(final) | 防止pairwise/首目标/静默截断伪装aggregate安全 | 2026-08-11 |
| VR-13 | DP-13 Observation health | OBSERVED/DEGRADED/COASTING/UNUSABLE与duty正交；uncertainty margin；UNUSABLE strict fail-stop；UNKNOWN_ROLE仍占风险容量 | 采纳(final) | 防止sensor failure伪装CLEAR/SUCCESS及cached-plan隐式fallback | 2026-08-11 |
| VR-14 | DP-14 Immutable handoff | frozen Cycle/Snapshot；epoch+cycle+input hash幂等；private-copy atomic step；decision commit与solver execution status分离；gap/reset显式 | 采纳(final) | 保证同证据同decision、异常不半更新且optimizer不反控规则状态 | 2026-08-11 |
| VR-15 | DP-15 Lifecycle observability | typed snapshot/event子schema；major/minor兼容；bounded live ring+incremental sink；canonical Planner ODD hash；GUI区分Planner/Evaluator来源 | 采纳(final) | 使decision因果、版本、参数和运行证据可审计且内存有界 | 2026-08-11 |
| VR-16 | DP-16 L0/L1 acceptance | A lifecycle contract→B mapping→C real-IPOPT closed-loop→D parity/full/runtime四层门；实际轨迹与独立Evaluator证据 | 采纳(final) | 防止仅G3/仅unit/self-evaluation/fallback/threshold weakening伪装能力完成 | 2026-08-11 |
| VR-17 | CARD-01 L0 module architecture & transaction | 采用Deep Transactional Lifecycle：neutral geometry→单一state owner→frozen Cycle/Snapshot→L1 Assembler→solver；decision commit与solver execution分离 | 采纳(final) | 保持L0/L1责任、幂等atomic handoff和独立测试；IPOPT失败不阻止world/rule state推进 | 2026-08-11 |
| VR-18 | CARD-02 Observation identity & degraded tracking | 采用Tracker-Authoritative Rich Contract：Tracker权威提供`id+generation`、track status/time/covariance/provenance；Builder标准化；Lifecycle只拥有episode/duty | 采纳(final) | 避免adapter/Lifecycle猜测identity与freshness；支持coasting/reacquisition/UNUSABLE可审计处理 | 2026-08-11 |
| VR-19 | CARD-03 Pairwise COLREG decision lifecycle | 采用Orthogonal Deterministic FSM；固定顺序推进health/identity→classification→risk→lock→action/side→Rule17→achievement/release/rearm | 采纳(final) | 保持规则语义、cycle freeze与独立可测；避免statechart engine复杂度和score权重隐式改写duty | 2026-08-11 |
| VR-20 | CARD-04 Multi-target maneuver resolution | 采用Constraint-Set Aggregation + Single NLP；全部pairwise state后求共同course/speed集合，显式conflict/capacity/core-capability gate | 采纳(final) | 防止首目标/全局side覆盖冲突和静默截断；保持一次all-target IPOPT及decision/execution单向边界 | 2026-08-11 |
| VR-21 | CARD-05 Evidence, compatibility & acceptance | 采用Typed Schema + bounded live ring/incremental sink + A/B/C/D layered gates；Planner/Evaluator profile与证据来源分离 | 采纳(final) | 使L0 transition、L1 mapping、real-IPOPT行为和8010/full regression形成可复现证据链 | 2026-08-11 |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|----|------|----------|--------|
| ALT-01 | 只拆 `_target_decisions` helper | 状态、事务、reset、evidence 与 aggregate 仍散在 facade | VR-01 |
| ALT-02 | Lifecycle 同时拥有 LOS、Problem Assembly、IPOPT | 业务状态与数学/solver artifacts 耦合，无法独立 contract test | VR-01 |
| ALT-03 | evaluator FSM/classifier 直接成为 planner authority | planner/evaluator 共同决策形成自评耦合 | VR-01 |
| ALT-04 | Mid 继续 import `evaluation.classify_geometry` | 包依赖方向错误，evaluator label/fallback 演进会直接改变控制 | VR-02 |
| ALT-05 | Lifecycle 复制全部 geometry/classifier 公式 | 物理数学、单位、角度 wrap 与符号容易漂移 | VR-02 |
| ALT-06 | Evaluator FSM verdict 直接进入 PlannerInput | 评分器成为控制 authority，闭环验收可能自证 | VR-02 |
| ALT-07 | 每周期 stateless classify→intent | ownship 改向会造成 label flicker，并丢失 commitment/Rule17/release duty | VR-03 |
| ALT-08 | 单一 enum 编码 encounter×role×phase×side×health | 组合爆炸、非法状态难审计、扩展破坏兼容 | VR-03 |
| ALT-09 | 复用 evaluator `PairwiseColregFSM` | 评分状态不覆盖 planner commitment、generation、coasting、aggregate conflict 与 atomic handoff | VR-03 |
| ALT-10 | Lifecycle 直接消费 `PlannerInput/TrackedObstacle` | 泄漏 route/tracker/adapter 且现有字段缺 generation/真实 age/maneuverability | VR-04 |
| ALT-11 | Observation 只含 ID/position/velocity | 无法判断 stale、identity reuse、uncertainty、low-speed validity 或 dynamic clearance | VR-04 |
| ALT-12 | 缺失 generation/age/heading 填 0 或当前时间 | 把未知伪装成确定事实，导致错误 classification/release/rearm | VR-04 |
| ALT-13 | 继续使用 `crossing_give_way` 等组合字符串 | encounter、role、risk、action 焊死，无法支持 Rule17/lock/镜像审计 | VR-05 |
| ALT-14 | 只有达到 DCPA/TCPA 风险阈值才分类 | 无法提前 monitor/lock，风险 profile 会重写规则事实 | VR-05 |
| ALT-15 | 低速/边界/缺失 fallback 为 CLEAR 或最近 label | 产生危险假阴性；无证据历史保持应归 DP-07 | VR-05 |
| ALT-16 | `action_lead_time = horizon_steps × horizon_dt` | 业务进入绑定 optimizer 离散化，1200s horizon 会导致极早 commitment | VR-06 |
| ALT-17 | 复用 evaluator risk/stage/50m gate | acceptance profile 反向控制 planner，50m 也不是通用 action-entry 值 | VR-06 |
| ALT-18 | 只用 DCPA、只用 TCPA 或只用 range | 分别产生远期误触发、安全通过误触发或无法表达 closing future risk | VR-06 |
| ALT-19 | Candidate 出现立即 commit | 噪声/边界抖动制造 flicker；urgent 已有独立 bypass | VR-07 |
| ALT-20 | 按固定 solve cycles 确认 | 调度频率、hold、retry 改变业务时间语义 | VR-07 |
| ALT-21 | exact label 变化必重置或 same-role 无条件合并 | 前者过度敏感，后者掩盖不同 constraint semantics | VR-07 |
| ALT-22 | 固定5°且minimum row只首轮激活 | 动作不明显、约束消失，真实轨迹可近似直线 | VR-08 |
| ALT-23 | HO/CS/OT统一固定30° | 30°不是规则常数，忽略船型、时间、净空、route和多目标可行性 | VR-08 |
| ALT-24 | OT固定STARBOARD passing | Rule13不规定passing side，可能拒绝更安全可行的port corridor | VR-08 |
| ALT-25 | crossing-stand-on/overtaken 永久HOLD | 缺少17(a)(ii)/(b)升级，非合作目标只能被动进入危险 | VR-09 |
| ALT-26 | 仅固定TCPA阈值切MAY/MUST | 忽略target action adequacy、净空与target-alone capability | VR-09 |
| ALT-27 | Rule17(c)泛化为所有阶段/场景永久禁止port或强制starboard | 扩大条文范围，并可能与17(b)/多目标即时危险冲突 | VR-09 |
| ALT-28 | `signed_tcpa<=0`或CPA node通过即release | 不证明船体让清、持续分离或恢复轨迹安全 | VR-10 |
| ALT-29 | 固定190m或`k*own_length` | 无规则来源，忽略target尺度、相对速度、机动能力与passing axis | VR-10 |
| ALT-30 | PAST_CLEAR立即删state，或完全回route才release | 前者丢失恢复期re-risk，后者把route tracking误作COLREG duty条件 | VR-10 |
| ALT-31 | 永久`released_target_ids` | 同一目标二次风险被屏蔽 | VR-11 |
| ALT-32 | 目标缺失一周期立即删除state | 瞬时漏检消除commitment/Rule13 duty，恢复后重新抖动 | VR-11 |
| ALT-33 | 仅裸target_id，无generation/discontinuity/tombstone | ID reuse继承旧动作，tracker身份语义不可审计 | VR-11 |
| ALT-34 | 最早TCPA或`any mandatory starboard wins`决定aggregate side | 可把Ship0转入第三目标并隐藏constraint conflict | VR-12 |
| ALT-35 | facade先排序`[:16]`再做lifecycle/aggregation | 第17个active threat静默消失，capacity错误不可见 | VR-12 |
| ALT-36 | pairwise各自合规即可推出aggregate安全 | pairwise可行不保证存在共同course/speed解 | VR-12 |
| ALT-37 | 无效/缺失track等于“没有目标”并返回SUCCESS | sensor failure与真实clear同形，形成危险假安全 | VR-13 |
| ALT-38 | UNUSABLE时继续执行cached old plan | 属未声明fallback，计划随时间失效，违反strict no-fallback | VR-13 |
| ALT-39 | 忽略covariance/degraded或UNKNOWN_ROLE不占capacity | 系统性隐藏不确定性和未分类威胁 | VR-13 |
| ALT-40 | facade逐dict/set mutation后调用solver | partial mutation、retry非幂等、异常污染与职责混合 | VR-14 |
| ALT-41 | 只用sim_time或solve_id，无epoch/input hash | reset复用、same-time不同输入和失败retry无法区分 | VR-14 |
| ALT-42 | solver成功才提交Lifecycle，或solver失败回滚decision | optimizer结果反向控制world/rule transition，retry重复event | VR-14 |
| ALT-43 | 自由格式Lifecycle fields散放`algorithm_details`且无子schema | 字段drift，消费者无法区分缺失/旧版/语义变更 | VR-15 |
| ALT-44 | 内存保存全部history，或只保存latest无event sink | 前者无界增长，后者无法审计transition因果 | VR-15 |
| ALT-45 | hash含绝对路径的resolved profile，或只记录build hash | 跨checkout不稳定且不能证明Planner ODD参数身份 | VR-15 |
| ALT-46 | 只看Playground未碰撞或G3 PASS | 无法证明role、side、substantial action、Rule17、release/rearm或atomic contract | VR-16 |
| ALT-47 | 只做unit/fixture，不跑real IPOPT closed-loop与8010 | 无法证明L0→L1→solver→Ship真实执行与GUI证据链 | VR-16 |
| ALT-48 | planner/evaluator共享expected label，失败时fallback、改场景或降低阈值 | 自证、阈值作弊并隐藏能力边界 | VR-16 |
| ALT-49 | Assembler-Embedded Transaction Engine | migration短，但solver成功成为authoritative lifecycle提交条件；IPOPT失败会冻结规则/时间状态，engine责任过宽 | VR-17 |
| ALT-50 | Event-Sourced Per-Target Actors | replay/跨进程恢复强，但当前单进程Playground不需要journal/actor/coordinator/projector，新增故障面不提升COLREG算法 | VR-17 |
| ALT-51 | Adapter-Synthesized Compatibility Contract作为最终架构 | 旧tuple不能可靠区分fresh/coasting或same-ID reuse；cache heuristics形成第二套tracker | VR-18 |
| ALT-52 | Lifecycle-Owned Tracking State | 复制association/KF职责并扩大故障域；不同COLAV算法可能形成不同track truth | VR-18 |
| ALT-53 | Hierarchical Statechart作为pairwise authority | 可视化强，但正交parallel regions仍需FSM invariant/merge规则，并新增event ordering、history与engine故障面 | VR-19 |
| ALT-54 | Reactive Risk-Scoring作为pairwise lifecycle authority | 连续评分适合候选排序，不适合决定Rule13 duty、Rule17法律阶段和release事实；权重调参会隐式改规则状态 | VR-19 |
| ALT-55 | Multi-Mode Enumeration + Multiple NLP Solves | 非凸mode比较强，但多次cold-start IPOPT放大deadline；solver胜者若决定commitment会破坏CARD-01单向事务 | VR-20 |
| ALT-56 | Sequential Priority Arbitration | 实现短但pairwise priority不证明共同安全；补全全部target veto/修正后实质退化为constraint-set aggregation | VR-20 |
| ALT-57 | Event-Sourced Audit作为control state authority | replay强，但journal I/O/projection进入控制关键路径并推翻CARD-01同步state owner；当前Playground需求过重 | VR-21 |
| ALT-58 | Trace-Only Scenario Acceptance | 迁移最短，但自由格式outcome trace不能证明transition/identity/Rule17/atomic contract或consumer兼容 | VR-21 |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|----|------|----------|-----------|------|-------------|-----------|
| TS-01 | 坐标系 | L0/L1统一ENU，数组顺序north/east | m、m/s | R1/R34 | DP-02/04；Cycle/Observation | x/y改为显式N/E语义 |
| TS-02 | 坐标系 | heading/course从North顺时针为正 | rad；0=N，pi/2=E | PROJECT_FACT+DESIGN_DECISION | DP-04/08；geometry/core | 固化cos→N/sin→E |
| TS-03 | 坐标系 | body/route x-forward、y-starboard；cross-track正=starboard | ENU projection | DESIGN_DECISION | DP-08/12/14；Aggregate | 替代隐式side sign |
| TS-04 | 坐标系 | relative position=`target-ownship`；PassingCorridor用`ownship-target`投影目标starboard normal | 正=TARGET_TRACK_STARBOARD | R30+DESIGN_DECISION | DP-08/15；geometry/evidence | 消除passing side歧义 |
| TS-05 | 坐标系 | L0不收WGS84/UTM；上游转ENU；solver原点=solve-time ownship | explicit transform | R3/R40 | DP-01/04/14；Builder | facade隐式映射改显式证据 |
| TS-06 | 物理量单位 | 内部统一SI/rad/s；deg仅配置/UI边界 | m,s,m/s,m/s²,rad,rad/s | R1/R13/R16 | DP-04/14；全部接口 | YAML deg进入profile即转rad |
| TS-07 | 物理量单位 | track state/cov layout=`[N,E,VN,VE]`，4×4对称PSD | covariance按维度乘积 | R34/R38/R39 | DP-04/13；TrackSnapshot | schema显式layout |
| TS-08 | 物理量单位 | hull position为几何中心；clearance为footprint边到边 | m | R12/R25 | DP-06/10/16 | 与中心距/半径补偿证据分开 |
| TS-09 | 符号约定 | 普通角wrap到`(-pi,pi]`；commit baseline可unwrapped连续保存 | rad | DESIGN_DECISION | DP-07/08/14 | 禁止每周期累加 |
| TS-10 | 符号约定 | signed TCPA正=未到CPA，零=CPA，负=已通过；DCPA非负且带validity | s、m | R15/R19 | DP-05/06/10 | 固化未成文语义 |
| TS-11 | 时序约定 | Lifecycle唯一时间基准sim time；全部timer用物理秒 | s | R41+DESIGN_DECISION | DP-06/07/10/11/14 | 不按solve次数 |
| TS-12 | 时序约定 | cycle identity=`epoch,sequence,input_hash`；同key同hash幂等；同key异hash=INPUT_CONFLICT | canonical hash | R40/R43/R44 | DP-14/15；step | 替代solve_id/sim_time alone |
| TS-13 | 时序约定 | solve=5s、deadline=20s；gap>`max(2*solve,solve+dt_sim)`=TIME_GAP | s | PROJECT_FACT+DESIGN_DECISION | DP-14；Adapter | 增加大gap门 |
| TS-14 | 时序约定 | 80个15s control intervals=1200s；public 81 state samples t=0..1200 | N=80、dt=15s | MASS parity+DESIGN_DECISION | DP-14/15/16；Core/GUI | 当前80 points t=0..1185需修正 |
| TS-15 | 时序约定 | solver失败不回滚decision；hold不推进Lifecycle；typed input/conflict failure不solve、不cached | strict no fallback | VR-17/18/20 | DP-13/14；Adapter | 拆开decision/execution |
| TS-16 | 数值边界 | max required targets=16；先处理全部tracks，超限CAPACITY_EXCEEDED | count | PROJECT_FACT+VR-20 | DP-12/14 | 删除`[:16]` |
| TS-17 | 数值边界 | fresh≤1s；usable≤5s；reacquire=5s；tombstone=10s | s | PROJECT_FACT+DESIGN_DECISION | DP-11/13 | 不再缺age默认0 |
| TS-18 | 数值边界 | COG valid SOG≥0.25m/s；cov eig≥-1e-9；Gaussian margin confidence=0.99 | m/s、probability | R37/R39+DESIGN_DECISION | DP-04/13 | low-speed/cov进入health |
| TS-19 | 数值边界 | Planner ODD hard hull margin=50m、comfortable=150m；center门加双方support+uncertainty | m | R12/R25+DESIGN_DECISION | DP-06/10/16 | 与Evaluator profile分hash |
| TS-20 | 数值边界 | risk candidate=role/approaching/positive TCPA且预测clearance<150m；确认5s；urgent按50m或required-response TCPA | s、m | R14/R15/R19+DESIGN_DECISION | DP-06/07 | 不绑定1200s horizon |
| TS-21 | 数值边界 | substantial commitment补足安全缺口并动力学可达；baseline固定、持续到actual achievement | outcome-based | R14/R17/R28/R30 | DP-08/16 | 无固定5°/统一30°/successive increments |
| TS-22 | 数值边界 | Rule17 window=10s；MAY看不适当动作+target-alone仍可行；MUST看target-alone无50m safe action或urgent | s、m | R14/R27/R29+DESIGN_DECISION | DP-09 | 替代永久HOLD/单TCPA |
| TS-23 | 数值边界 | release确认10s；联合valid、CPA passed、separating、future guard、dynamic hull margin公式 | s、m | R12/R13/R25/R26+DESIGN_DECISION | DP-10/11 | 删除190m/单TCPA |
| TS-24 | 数值边界 | OT双侧先最大化clearance再最小化deviation；数值并列starboard仅deterministic tie-break；commit后锁侧 | ordered criteria | R14/R17/R24/R30 | DP-08/12 | 不固定starboard |
| TS-25 | 数值边界 | priority=MUST>locked/mandatory>candidate>MAY>watch>monitor；空集CONFLICT；speed/STOP允许，STOP下界0 | ordered constraints | R14/R31/R33 | DP-12 | 替代first/any-starboard，修正speed floor |
| TS-26 | 接口语义 | Tracker输出immutable TrackSnapshot含key/status/state/cov/hull/time/source/quality/optional dynamics | typed DTO | VR-18 | DP-04/11/13；Tracker→Builder | 替代裸tuple |
| TS-27 | 接口语义 | Builder只验证/标准化/派生facts+health；未知不填0；Planner/Evaluator独立解释 | pure mapping | VR-02/18 | DP-02/04/13 | 移除Evaluator classifier authority |
| TS-28 | 接口语义 | `Lifecycle.step(cycle)`同步pure-transition；private-copy+invariants后atomic commit；reset含epoch/reason | immutable API | VR-17/19 | DP-01/03/14 | 替代逐dict/set mutation |
| TS-29 | 接口语义 | Snapshot含全部pairwise/aggregate/events/profile hash，不含CasADi/IPOPT objects | frozen schema | VR-01/19/20 | DP-03/14/15；L0→L1 | 替代locals/hidden containers |
| TS-30 | 接口语义 | L1只映射Snapshot+LOS；无法表达per-target/STOP时CORE_CAPABILITY_MISMATCH；core只求解 | strict mapping | VR-17/20 | DP-01/12/14；Assembler/Core | 禁止global side collapse |
| TS-31 | 接口语义 | 明确UNUSABLE/INPUT_CONFLICT/TIME_GAP/MANEUVER_CONFLICT/CAPACITY/CORE_MISMATCH statuses，带owner/evidence | typed failure | VR-13/14/20 | DP-12/13/14；Adapter | 细化泛化INVALID/NUMERICAL |
| TS-32 | 接口语义 | reset清active/tombstones/LOS/warm/cache，epoch+1并记reason；rewind/restart/algorithm或authority change触发 | reset contract | R40/R41+DESIGN_DECISION | DP-11/14/15 | 当前无epoch/reason |
| TS-33 | 接口语义 | 保留PlannerTrace1.x，新增versioned lifecycle子文档/events；minor additive、breaking升major | schema semver | R42/R43+VR-21 | DP-14/15；Trace | 替代自由字典 |
| TS-34 | 接口语义 | live ring=1024 events；完整JSONL增量sink；overflow计数；sink failure=EVIDENCE_INCOMPLETE | bounded/durable | R42/R46+DESIGN_DECISION | DP-15/16；Session | 替代无界内存 |
| TS-35 | 接口语义 | resolved Planner ODD canonical JSON SHA-256，不含绝对路径；build/planner/evaluator hash分离 | stable hash | R43/R44 | DP-15；Trace/Manifest | 修正路径/单build identity |
| TS-36 | 接口语义 | GUI分Planner/Evaluator；显示81-point/1200s、lifecycle、targets、aggregate、IPOPT；capability经A/B/C/D门 | source-separated evidence | VR-21 | DP-15/16；GUI/Capability | 修正来源混合/时间网格/G3边界 |

---

## 参考文献

- [R1] Colav-Simulator current workspace: colav_simulator/integrations/mid_mpc_ipopt.py:72-356,466-480; colav_simulator/evaluation/encounter.py:125-187; colav_simulator/evaluation/colreg_fsm.py:12-94; colav_simulator/core/colav/custom_mpc_adapter.py:196-332.
- [R2] Colav-Simulator tests/capabilities: tests/test_mid_mpc_ipopt_integration.py; tests/test_mid_mpc_single_encounter.py; tests/test_mid_mpc_multiship_runtime.py; colav_simulator/experiment/capabilities.py:118-133,215-476.
- [R3] /Users/marine/Desktop/MPC/M5_MPC_业务流程分层架构.md, especially §3 L0, §4 L1.6, §7 L4.3, §8 LX.
- [R4] MASS-L3 GitLab l3-tdl@4c8ff3bd37591b3bc301537eae8876c25b208bf8: mid_mpc_input_builder.hpp; plan_decider.hpp; mid_mpc_diagnostic_capture.hpp. Mid-MPC files与前次 bf5de9e0 审查无差异。
- [R5] B.-O. H. Eriksen, G. Bitar, M. Breivik, A. M. Lekkas, “Hybrid Collision Avoidance for ASVs Compliant with COLREGs Rules 8 and 13–17,” Frontiers in Robotics and AI 7:11, 2020, doi:10.3389/frobt.2020.00011.
- [R6] International Maritime Organization, “Convention on the International Regulations for Preventing Collisions at Sea, 1972 (COLREGs),” official convention overview.
- [R7] H. He et al., “COLREGs-compliant model predictive collision avoidance for autonomous ships in restricted environments,” Ocean Engineering 338, 2025, doi:10.1016/j.oceaneng.2025.121966.
- [R8] U.S. Coast Guard Navigation Center, “Amalgamated Navigation Rules: Rules 13, 14, 16 and 17,” official rule text, https://navcen.uscg.gov/navigation-rules-amalgamated.
- [R9] P. N. Hansen et al., “COLREGs-based Situation Awareness for Marine Vessels - a Discrete Event Systems Approach,” IFAC-PapersOnLine 53(2), 2020, doi:10.1016/j.ifacol.2020.12.1453.
- [R10] K. Bergman et al., “A COLREGs-Compliant Motion Planner for Autonomous Maneuvering of Marine Vessels in Complex Environments,” 2020, arXiv:2012.12145.
- [R11] MASS-L3 GitLab l3-tdl@4c8ff3bd37591b3bc301537eae8876c25b208bf8: m5_tactical_planner/common/activation_fsm.hpp.
- [R12] L. Du et al., “An empirical ship domain based on evasive maneuver and perceived collision risk,” Reliability Engineering & System Safety 213, 2021, doi:10.1016/j.ress.2021.107752.
- [R13] International Maritime Organization, Resolution MSC.137(76), “Standards for Ship Manoeuvrability,” 2002.
- [R14] U.S. Coast Guard Navigation Center, “Navigation Rules and Regulations Handbook,” corrected 2024, Rules 7, 8, 13, 14, 16, 17, https://www.navcen.uscg.gov/sites/default/files/pdf/navRules/Handbook/NavRules_Handbook_Corrected_08_08_2024.pdf.
- [R15] International Maritime Organization, Resolution MSC.192(79), “Adoption of the Revised Performance Standards for Radar Equipment,” 2004, §§5.25, 5.27, 5.29, 5.31.
- [R16] International Maritime Organization, Resolution A.601(15), “Provision and Display of Manoeuvring Information on Board Ships,” 1987.
- [R17] I. B. Hagen et al., “Exploration of COLREG-relevant Parameters from Historical AIS-data,” Journal of Navigation 77, 2024, doi:10.1017/S0373463324000109.
- [R18] A. Bąk et al., “Factors Influencing the Action Point of the Collision Avoidance Manoeuvre,” Applied Sciences 11, 7299, 2021, doi:10.3390/app11167299.
- [R19] J. Ha, M.-I. Roh, H.-W. Lee, “Quantitative calculation method of the collision risk for collision avoidance in ship navigation using the CPA and ship domain,” Journal of Computational Design and Engineering 8(3), 2021, doi:10.1093/jcde/qwab021.
- [R20] T. Tengesdal, E. F. Brekke, T. A. Johansen, “On Collision Risk Assessment for Autonomous Ships Using Scenario-Based MPC,” 2020, §§2.2, 6.
- [R21] K. Woerner et al., “Quantifying protocol evaluation for autonomous collision avoidance,” Autonomous Robots 43, 2019, doi:10.1007/s10514-018-9765-y.
- [R22] MASS-L3 Tactical Layer current local source: `m6_colregs_reasoner/encounter_state_machine.hpp`, `encounter_state_machine.cpp`, `types.hpp`.
- [R23] P. N. Hansen et al., “Probabilistic COLREGs Classification,” arXiv:2402.05662, 2024.
- [R24] Otal Investments Ltd. v. M/V Clary, U.S. Court of Appeals, Second Circuit, 2007.
- [R25] N. Wang, “A Novel Analytical Framework for Dynamic Quaternion Ship Domains,” Journal of Navigation 66, 2013, doi:10.1017/S0373463312000483.
- [R26] T. A. Johansen et al., “Autonomous Marine Operation and Systems,” COLREG collision-avoidance architecture paper, 2016, https://torarnj.folk.ntnu.no/colregs_cams.pdf.
- [R27] The Dream Star [2017] SGHC 220, Singapore High Court, paras.97-100.
- [R28] Marine Accident Investigation Branch, “Collision between Scottish Viking and Homeland,” Report 4/2011, §§2.6-2.7.
- [R29] L. Du et al., “Intention detection of ships from action observations,” Ocean Engineering 201, 107110, 2020, doi:10.1016/j.oceaneng.2020.107110.
- [R30] R. Zaccone et al., “COLREG-Compliant Ship Collision Avoidance Based on Path Geometry,” Journal of Marine Science and Engineering 9, 405, 2021, doi:10.3390/jmse9040405.
- [R31] Y. He et al., “Collision-avoidance path planning for multi-ship encounters considering ship manoeuvrability and COLREGs,” Transportation Safety and Environment 3(2), 2021, doi:10.1093/tse/tdab006.
- [R32] R. Sawada et al., “Multi-Ship Collision Avoidance Validation with Imazu Scenarios,” Journal of Marine Science and Engineering 9, 790, 2021, doi:10.3390/jmse9080790.
- [R33] MASS-L3 Tactical Layer current local source: `l3_risk_model/risk_model.cpp`, `risk_model.hpp`, `test_risk_model.cpp`.
- [R34] Colav-Simulator current workspace: `colav_simulator/core/tracking/trackers.py`; `colav_simulator/core/colav/custom_mpc_adapter.py:195-291,453-499`; `colav_simulator/integrations/mid_mpc_ipopt.py:72-94,223-327,358-381`; `tests/test_mid_mpc_ipopt_integration.py:265-287`.
- [R35] International Maritime Organization, Resolution MSC.192(79), §§5.5.5-5.5.6, §§5.25.4-5.29; Resolution MSC.112(73), AIS presentation performance standards.
- [R36] Kufoalor et al., “Autonomous Maritime Collision Avoidance: Field Verification of Autonomous Surface Vehicle Behavior,” ECC 2019; local `vimmjipda` initiator/terminator/interface sources.
- [R37] T. I. Fossen and S. Fossen, “Five-State Extended Kalman Filter for Estimation of Speed Over Ground and Course Over Ground of a Dynamic Positioning Ship,” Sensors 21(23), 7910, 2021, doi:10.3390/s21237910.
- [R38] EUROCONTROL, “ASTERIX Category 062: System Track Data,” Edition 1.21, 2025, I062/080 and I062/500.
- [R39] NIST/SEMATECH e-Handbook, Chi-Square Distribution; Zhang et al., “Chance-Constrained Collision Avoidance for MAVs,” arXiv:2006.07907, 2020.
- [R40] Colav-Simulator current workspace: `colav_simulator/core/ship.py:585-607,921-950`; `custom_mpc_adapter.py:38-96,228-278,392-435,512-689`; `simulator.py:395-438`; `experiment/session.py:53-175`; `gui_server/main.py:346-501`.
- [R41] ROS 2 Design, “Clock and Time”; ROS 2 `rcl` time jump callback API, https://design.ros2.org/articles/clock_and_time.html.
- [R42] Colav-Simulator current workspace: `diagnostics.py:53-137`; `experiment/session.py:32-175`; `experiment/persistence.py:73-96`; `integrations/registry.py:300-396`; `gui_server/main.py:649-780`; `web_gui/app.js:1504-1700`; `tests/test_mid_mpc_single_encounter.py:100-188`; `tests/test_mid_mpc_multiship_runtime.py:20-106`; `evaluation/evaluator.py:270-350`.
- [R43] Cloud Native Computing Foundation, “CloudEvents Specification”; OpenTelemetry, “Logs Data Model,” “Telemetry Schemas,” “Telemetry Stability,” and “Logs SDK”; Semantic Versioning 2.0.0.
- [R44] IETF RFC 8785, “JSON Canonicalization Scheme,” 2020.
- [R45] U.S. Coast Guard Rules 8 and 16 [R14] plus Colav-Simulator actual trajectory/evaluator project facts listed in [R42].
- [R46] OpenTelemetry Logs SDK specification; Python 3 `collections.deque` documentation.

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点  [2026-08-10 18:18]

- 模式判定: **重构**。现有 Colav 已有真实运行 implementation、固定场景 evidence 与薄弱的隐式 encounter memory；目标是深化，不全盘重写。[R1][R2]
- 代码快调: 当前 _MidMpcFacade.solve/_target_decisions 同时拥有 classification、role、commit course、release、rearm suppression、sorting、aggregation、row-schedule handoff；L0/L1 locality 不足。[R1]
- 设计意图快调: 七层文档要求 L0 标准化业务输入、L1.6 Rule-to-Constraint mapping，并由 LX 记录 activation/transition evidence。[R3]
- 远端快调: GitLab 当前远端已把 input assembly 和 plan decision 抽为 pure seams；可借鉴 module 深度，不移植 ROS2、M4/M6、BC-MPC、GNC factors。[R4]
- 行业快调: Mid-level COLAV 的 COLREG interpretation 通常需要显式 state machine；输入至少包含 geometry、CPA distance/time，且需覆盖多目标同时规则。[R5]
- 规则快调: Rules 13–17 的 give-way/stand-on 责任不同；Rule 17 包含 stand-on 在对方未采取适当行动时的升级动作，因此 HOLD 不能是无条件永久状态。[R6]
- 技术分解: 新增 TD-01，完整展开 observation、classification、risk entry、lock、intent、stand-on escalation、release、rearm、multi-target、degraded input、handoff、evidence。
- 新增决策点: DP-01..DP-16。
- 新增盲区: BL-01..BL-09。
- 新增场景: SC-01..SC-09。
- NLM 快调失败: 本机 SOCKS proxy 缺少 socksio；未修改环境，改用 IMO 与一手论文快调。记录为 BL-09，不伪装闭环。

### Step1 · 远端与规则证据刷新  [2026-08-11 09:00]

- GitLab 远端已前进至 `4c8ff3bd37591b3bc301537eae8876c25b208bf8`；Mid-MPC 相关文件相对 `bf5de9e0` 无差异，R4 provenance 更新。[R4]
- 新远端加入 pure `activation_step` module，以持续失败进入、单次成功恢复的非对称 hysteresis 作为可测试 project pattern；该事实只用于发现 DP-06/DP-07，不预判 encounter lifecycle 应复用同一阈值。[R11]
- USCG 正式规则确认：Rule 13 规定 overtaking 责任持续到 finally past and clear；Rule 16 要求 early and substantial action。规则文本未规定 overtaking 必须选择 starboard side，因此新增 BL-10/BL-11，等待用户与后续证据裁决。[R8]
- 一手论文补强技术分解：逐船有限状态自动机可分离 situation understanding 与 anticipation；连续优化可在一个 planning cycle 内冻结离散 COLREG state，避免 solver 内部标签跳变。[R9][R10]
- Step1 决策点保持 DP-01..DP-16；新增盲区 BL-10..BL-11。未形成任何 VR/ALT/TS 裁决。

### Step2 · grilling 压力测试  [2026-08-11 09:02]

#### DP-01 · Encounter Lifecycle module 责任范围

- 专家: 离散 encounter lifecycle 与连续优化分离；一个 solve cycle 内 lifecycle decision 保持固定。[R9][R10]
- 新手: 只抽取 `_target_decisions` 会留下 commitment state、release、rearm 与 aggregation 泄漏，是 shallow pass-through。
- 悲观: 若 module 同时拥有 LOS、target prediction、row schedule、IPOPT 与 L4 acceptance，则形成新的巨型 facade，破坏 L0→L1→L3→L4 单向责任。
- 默认最简版失效: 只包装 geometry classification 不通过 deletion test；删除后核心复杂度不会重新分散。
- 用户确认的责任: module 拥有逐目标 lifecycle memory、entry/lock/commit/release/rearm、稳定 role/intent/side/commitment facts、多目标规则冲突、transition evidence、reset。
- 用户确认的非责任: LOS/route tracking、optimizer target selection、target motion prediction、CPA/row schedule/route frame、CasADi/IPOPT、L4 acceptance、solve deadline/fallback。
- 推荐 seam: PlannerInput adapter → Encounter Lifecycle → immutable decision facts → Problem Assembler；`_MidMpcFacade` 降为薄 orchestrator。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-02 · 态势分类权威来源

- 专家: 共享 geometry facts，不共享 planner decision state 或 evaluator verdict；situation facts 与 policy interpretation 分离。[R9]
- 新手: 直接复用 `evaluation.classify_geometry` 虽减少重复，但 evaluator profile、分类阈值和 risk distance 会反向控制运行时 Planner。
- 悲观: 完全复制两套 CPA/angle math 会产生单位、wrap 与数值 drift；共享完整 encounter label 又形成自评循环。
- 默认最简版失效: 只移动或重命名 `classify_geometry`，仍把 geometry、threshold、role 混在一个 shallow module。
- 用户确认的责任: planner-neutral geometry module 只产出 relative geometry、CPA、bearing、course/speed relation 与数据有效性；Encounter Lifecycle 独立分类/角色/阈值/hysteresis；Evaluator 独立拥有 profile、stage/FSM 与 verdict。
- 新增盲区: BL-12，Planner 分类角度、risk distance 和进入阈值的 ODD/profile provenance，优先级高。
- 用户确认: 2026-08-11，确认并纳入 BL-12。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-03 · Lifecycle 技术与状态表达

- 专家: 采用逐目标、确定性、有记忆的状态机；Rule 13 责任不因瞬时 bearing 改变而解除，一次连续优化期间离散状态固定。[R8][R9][R10]
- 新手: 每周期重新分类会因本船改向改变 relative bearing，产生 OT/clear/crossing flicker，继而丢失 commitment。
- 悲观: 单一巨型 enum 编码 phase×encounter×role×side×emergency×health 会状态爆炸。
- 默认最简版失效: CLEAR/COMMITTED/RELEASED 三态无法表达 monitor、stand-on escalation、track-loss、二次风险与 degraded observation。
- 用户确认的技术方向: pure per-target deterministic FSM；内部以 lifecycle phase、locked encounter、role、action mode、preferred side、commitment facts、observation health、transition evidence 等正交事实组合，不直接复用 evaluator PairwiseColregFSM。
- 新增盲区: BL-13，最小显式状态集合及正交分解，优先级高。
- 用户确认: 2026-08-11，确认并纳入 BL-13。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-04 · Pairwise observation contract

- 当前事实: `TrackedObstacle` 已包含 ENU position/velocity、covariance、船体尺度、`observed_at_s`、`age_s` 与 `degraded`；时间由 adapter 按 `sim_time-age` 合成。当前 contract 仅保证同周期 target_id 唯一，没有 track association generation。[R1]
- 专家: Lifecycle 应消费同一仿真时刻的 immutable pairwise snapshot；观测事实与 COLREG policy facts 分离，状态转移才能复现和审计。
- 新手: 直接把 `PlannerInput + TrackedObstacle` 传入 FSM 会泄漏 tracker、route、ENC 与 MPC execution interface，使 L0 成为 shallow pass-through。
- 悲观: ID 复用可让新目标继承旧 commitment；低速目标的 `atan2(v_e,v_n)` 会产生无意义 COG；陈旧或高不确定度观测若没有显式 health，可能误触发 release/rearm。
- 默认最简版失效: 只传 target ID、位置和速度，无法区分 stale/degraded/reused/low-speed observation，也无法审计某次 transition 的输入快照。
- 用户确认的 contract: L0 接收 immutable `PairwiseEncounterObservation`；包含 target identity、本船与目标的 ENU position/velocity、可用 heading/COG 及其有效性、船体尺度、中立 geometry/CPA/bearing facts、观测时间/age/covariance/degraded/validity reason；固定 ENU/SI/rad。
- 用户确认的非内容: observation 不包含 encounter label、role、GIVE_WAY/HOLD、preferred side、commit/release 或 MPC row schedule。
- 低速语义: 目标没有真实 heading 时只提供由速度导出的 COG；低于待裁决阈值时 COG 标记 invalid，不伪造航向。
- 新增盲区: BL-14 track association generation；BL-15 COG/quality/degraded thresholds，均为高优先级。
- 用户确认: 2026-08-11，确认并纳入 BL-14/BL-15。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-05 · 几何分类与角色映射

- 专家: classification、risk stage、role、action 必须正交；远距离目标仍可具有 OT/HO/CS 几何关系，只是尚未进入 action phase。
- 新手: `crossing_give_way` 等组合字符串看似简单，却把 encounter 与 ownship role 焊死，不利于 Rule 17 升级、双船对称性与证据审计。
- 悲观: 将无效、低速或角度边界歧义吞成 `clear` 会形成危险假阴性；必须保留 `UNDETERMINED/UNKNOWN`。
- 默认最简版失效: 当前 evaluator `classify_geometry` 先用 signed TCPA/DCPA 判 clear，再分类；Mid facade 又立即映射 intent/side，混合 geometry、risk、role、action。[R1]
- 用户确认的分类: `EncounterKind={HEAD_ON,CROSSING,OVERTAKING,CLEAR,UNDETERMINED}` 与 `OwnshipRole={GIVE_WAY,STAND_ON,MUTUAL_GIVE_WAY,NONE,UNKNOWN}` 为正交 facts。HO→MUTUAL_GIVE_WAY；右舷来船 crossing→GIVE_WAY；左舷来船 crossing→STAND_ON；本船追越→GIVE_WAY；本船被追越→STAND_ON。
- 用户确认的切分: DP-05 不以 DCPA/TCPA/range 决定 risk entry，不决定 HOLD/GIVE_WAY action、preferred side 或具体改向角；输出 instantaneous candidate，lock 归 DP-07；threshold provenance 来自独立 Planner ODD profile。
- 用户明确否决: 当前硬编码 `commit_course + 5°` 不符合项目对 Rule 8/16 “early and substantial”的解释；后续 DP-08 不得沿用连续小角度转向。目标是一次孤立、明显的大幅动作，用户以约 30° 为示例，最终幅度与可达性仍需证据裁决。
- 新增盲区: BL-16 分类角度/速度容差；BL-17 低速/边界歧义处理。BL-02 更新为 5° 已否决、具体 substantial-action contract 待 DP-08。
- 用户确认: 2026-08-11，确认并附加 substantial-action 约束。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-06 · 风险阶段与进入条件

- 专家: DCPA 与 TCPA 必须联合；DCPA 单独会对遥远目标过早动作，TCPA 单独会对安全通过目标误动作。船体净空应显式从 center DCPA 与双方 footprint allowance 推导。
- 新手: 直接以 `horizon_steps × horizon_dt_s` 作为业务进入时间最简单，但修改数值离散便改变 COLREG 行为，违反 L0/L1 与 optimizer discretization 分离。
- 悲观: 复用 evaluator stage threshold 会让验收标准反向控制 planner；只使用瞬时 CPA 又可能忽略 nominal route 后续形成的风险。
- 默认最简版失效: 当前 `classify_geometry` 仅以 positive signed TCPA 与 DCPA risk distance 判 risk，没有最大 action lead time，极远 future CPA 也可立即 commit。[R1]
- 用户确认的 facts: `predicted_hull_clearance_m`、`approaching`、`action_entry_candidate`、`stand_on_watch_candidate`、`urgent_candidate`；名义 action entry 联合 own role、closing/positive TCPA、独立 `action_lead_time_s` 与 hull-clearance threshold。
- 用户确认的阶段: 有效相遇但无预测风险→MONITOR；give-way 风险→ACTION_CANDIDATE；stand-on 风险→WATCH_REQUIRED；近距离持续接近→URGENT_CANDIDATE。DP-07 决定 persistence/hysteresis/commit，DP-09 决定 stand-on escalation。
- 用户确认的切分: lifecycle 不读取 Mid-MPC 80×15s horizon；所有进入阈值属于独立 Planner ODD profile，不读取 evaluator profile。
- 新增盲区: BL-18 ODD thresholds；BL-19 instantaneous CPA 与 nominal-route prediction；BL-20 OT duty 与 risk threshold。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-07 · Lock-on 与 hysteresis

- 专家: entry 可短确认，exit 必须更严格；自身避让动作引起的 bearing/classification 改变不能解除原责任。[R8][R9][R10]
- 新手: 只缓存最近一次 non-clear 标签会让错误首帧永久锁定，不能替代 candidate persistence 与明确 phase transition。
- 悲观: 以连续 solve 次数计数会随 `solve_period_s` 改变业务行为；必须使用仿真物理时间。
- 默认最简版失效: 当前 `_committed_policies` 只缓存 action policy，encounter trace 仍输出 instantaneous label；release 后 `released_target_ids` 又永久禁止重入，不是完整 hysteresis lifecycle。[R1]
- 用户确认的 commit 前语义: 保存 candidate encounter/role/since；相同 risk candidate 持续 `entry_confirm_s` 后 commit；普通 candidate 变化重置计时；urgent candidate 可按独立条件绕过；全部使用秒。
- 用户确认的 commit 后锁定 facts: encounter、role、action mode、preferred side、commitment start/evidence，以及 DP-08 捕获的 course/reference。瞬时 classification 因本船动作改变时不得覆盖。
- 用户确认的允许变化: risk severity 升级、observation health、Rule 17 escalation、DP-10 release、reset；目标真实机动引起的受控重判留作 BL-22。
- 新增盲区: BL-21 entry/urgent 参数；BL-22 locked-fact reclassification；BL-23 同角色边界候选合并。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-08 · 行为意图与 substantial action

- 规则对齐: Rule 13 要求 overtaking vessel keep out of the way，且责任持续至 finally past and clear；没有规定必须从目标 port 或 starboard side 追越。Rule 8/16 要求 action early、positive/substantial、readily apparent，并避免 succession of small alterations。[R8]
- 专家: action 应表达为相对 commit 时刻 baseline course 的单个 absolute commitment；不能以每周期 current course 为基准滚动累加。
- 新手: “初始向右转”与“最终从目标右舷通过”不是同一事实；只检查 turn sign 不能证明 passing side。
- 悲观: 固定 30° 可能受动力学、ENC 或多目标限制；angle 是独立 ODD minimum candidate，不能被称为 COLREG 法定角度，也不能由 IPOPT 静默缩小。
- 默认最简版失效: 当前 `commit_course + 5°`，且 hard direction/minimum-alteration 仅 newly-committed 首轮 active；后续只跟踪小角度固定直线。[R1]
- 用户确认的 commitment shape: lifecycle 输出 action mode、turn direction、passing side、baseline course、minimum course change、absolute committed course、commit time 与 achievement state；L1 负责翻译，IPOPT 不拥有规则决定。
- 用户确认的 substantial-action 语义: 捕获一次 baseline，发布一次明显大幅 absolute target；未达到 minimum alteration 前约束持续 active，达到后保持至 release；风险显著升级时只允许产生可审计的离散 revision。约 30° 仅为候选示例，最终数值待 ODD/动力学证据。
- 用户修订 OT policy: 不强制 starboard-only。Rule 13 下 port/starboard 都可；按相对态势选择安全通过侧，避免机械执行。side 在 commit 时锁定，实际通过侧必须独立验证；具体 selection function 留作 BL-10/BL-25 与 DP-12 联合裁决。
- HO 仍按 Rule 14 使用 starboard alteration；CS/OT 动作需遵守各自 role 与安全通过语义，不从 Rule 13 推导固定侧。
- 新增盲区: BL-24 substantial angle/reachability；BL-25 passing-side proof；BL-26 discrete revision。
- 用户确认: 2026-08-11，确认 substantial commitment，随后明确取消 OT 固定右侧，改为按相对态势选择。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-09 · Rule 17 stand-on escalation

- 规则对齐: Rule 17(a)(i) 要求 stand-on 保持 course/speed；17(a)(ii) 在 give-way vessel 未采取 appropriate action 已明显时允许自主动作；17(b) 在仅靠 give-way vessel 已不能避免碰撞时要求采取最有助于避碰的动作；17(c) 对 crossing stand-on 的 port alteration 施加条件性限制。[R8]
- 专家: MAY_ACT 与 MUST_ACT 法律强度不同，不能压成单一 emergency flag。
- 新手: 只因 DCPA 小便立即打破 stand-on，会降低双方行为可预测性；必须先观察 give-way action adequacy。
- 悲观: 噪声轨迹可导致“目标未行动”误判；需要动作趋势、风险改善与物理持续时间共同形成证据。
- 默认最简版失效: 当前 Mid policy 将 crossing stand-on/overtaken 永久映射 HOLD，没有正式 escalation transition。[R1]
- 用户确认的 phases: STAND_ON→MAY_ACT→MUST_ACT。MAY_ACT 观察目标 course/speed action、predicted clearance improvement、independent latest-action time 与 persistence；MUST_ACT 使用更短 emergency window、critical clearance，以及目标单独行动能否解除风险的近似判断。
- 用户确认的 action constraint: crossing stand-on 在条件允许时不得向 port 转向位于本船 port side 的目标；优先 starboard alteration、减速或停车。该限制不泛化为所有 encounter 固定右转。
- 新增盲区: BL-27 appropriate-action evidence；BL-28 thresholds；BL-29 target-alone avoidability approximation；BL-30 multi-target Rule 17(c) conflict。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-10 · Release 与 past-and-clear

- 规则对齐: CPA 通过只是瞬时事实；Rule 8/13 要求检查动作效果并维持 overtaking responsibility，直至 finally past and clear。规则没有给出固定米数。[R8]
- 专家: release 必须联合 hull clearance、纵向超前、分离趋势、future clearance 与持续时间；route recovery 是 downstream action，不是 Rule 13 duty 结束的前置条件。
- 新手: 单帧距离增加可能来自噪声；`signed_tcpa<=0` 也不证明船体已经让清。
- 悲观: 过早恢复航路会再次切入目标轨迹；应先进入 PAST_CLEAR，授权 L1/LOS recovery，并由 L4 复核恢复轨迹。
- 默认最简版失效: 当前 HO/CS 以 signed TCPA≤0 release；OT 以固定 190m 纵向投影与总距离 release；没有 sustained separation、future clearance 或 dynamic footprint evidence。[R1]
- 用户确认的 phases: COMMITTED→PAST_CLEAR→RELEASED；PAST_CLEAR 要求 CPA passed、有效 observation、footprint-aware current clearance、持续分离、future clearance safe。OT 额外要求 target-frame longitudinal hull clearance、lateral clearance 与不再向目标航迹收敛。
- 用户确认的 recovery cut: lifecycle 输出 `route_recovery_allowed`；LOS/L1 决定恢复轨迹；L4 复核；恢复中重新形成风险交 DP-11 rearm。
- 用户要求并确认的阈值修订: 禁止固定 190m，也禁止单独 `k × own_length`。先扣除双方船体投影得到真实 longitudinal/lateral hull clearance，再以 `max(minimum_margin_m, size_factor × reference_length, relative_speed × response_guard_time)` 建立 dynamic margin；`reference_length` 至少考虑双方尺度，`response_guard_time` 考虑 course/speed time constant、required alteration/max turn rate。[R12][R13]
- 当前接口缺口: Ship 已向 COLAV kwargs 提供 `T_chi/T_U/r_max`，但 `PlannerInput` 没有保留这些 maneuverability facts；新增 BL-34。[R1]
- 新增盲区: BL-31 release ODD params；BL-32 recovery handoff/re-risk；BL-33 target-maneuver future horizon；BL-34 maneuverability contract。
- 用户确认: 2026-08-11，同意 footprint-aware + maneuverability-aware release guard。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-11 · Rearm、track loss 与 ID reuse

- 专家: release 结束一次 encounter episode，不是目标永久豁免；track association continuity 必须独立于裸 target_id。
- 新手: 目标缺失一帧便删除状态，会让 Rule 13/commitment duty 瞬间消失。
- 悲观: ID 复用可让新目标继承旧 action；永久 released set 又会让同一目标的真实二次风险被忽略。
- 默认最简版失效: 当前未见目标时当周期删除 commitment；持续可见 target_id 一旦加入 `released_target_ids` 便永久禁止 rearm；没有 generation/coasting/tombstone/reacquisition evidence。[R1]
- 用户确认的 identity: lifecycle key 为 `(target_id,generation)`；generation 应来自 tracker association。旧 tracker 暂可 generation=0，但必须标为 degraded contract；不可能的位置/速度跳变形成 identity-discontinuity evidence。
- 用户确认的 track-loss phases: OBSERVED→COASTING→LOST。coast timeout 内保留 locked facts；同 generation 在 reacquisition window 内恢复原 episode；超时保留有限 TTL tombstone；新 generation 不继承旧 commitment。
- 用户确认的 rearm sequence: PAST_CLEAR→观察安全分离区间→重新 approaching→重新满足 entry criteria→重新经过 entry confirmation。未完成 PAST_CLEAR 前风险恶化属于原 commitment escalation，不是 rearm。
- 用户确认取消永久 `released_target_ids`；reset 清空所有 active state 与 tombstones。
- 新增盲区: BL-35 generation；BL-36 time windows；BL-37 discontinuity；BL-38 coasting action。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-12 · 多目标 aggregation

- 专家: pairwise COLREG compliance 不能推出 aggregate maneuver compliance；必须先保留全部 pairwise duties，再解规则冲突。
- 新手: 让最早 TCPA target 单独决定 side，会忽略另一目标形成的禁止区域。
- 悲观: `any mandatory starboard wins` 仍可把 ownship 转入第三目标；容量截断更可能静默丢弃 active threat。
- 默认最简版失效: 当前 `_target_decisions` 返回排序前 16；aggregate 为存在 mandatory-starboard 即 starboard，否则取首个 give-way side；不能表达左右同时受阻、Rule 17 conflict 或 capacity overflow。[R1]
- 用户确认的顺序: all observations→all per-target lifecycle decisions→rule-conflict aggregation→immutable aggregate directive→L1 risk selection of at most 16 NLP targets。Lifecycle state 不受 16-target core limit。
- 用户确认的 priority: MUST_ACT→committed give-way→ACTION_CANDIDATE→MAY_ACT→stand-on watch→monitor；同层按 time-to-violation、TCPA、predicted/current hull clearance、stable identity 排序。
- 用户确认的 constraint semantics: HO starboard 与适用的 Rule 17(c) restriction 属 mandatory；CS avoid-ahead 是 passing constraint；OT side 是 commit 前 preference、commit 后 locked。双方 course action 都受阻时输出 MANEUVER_CONFLICT，允许 L1 考虑 substantial speed reduction/stop，不静默选择首目标。
- 用户确认的 capacity: 所有 active/committed/urgent targets 必须入 NLP；余槽才放 monitor；active>16 显式 CAPACITY_EXCEEDED，禁止丢弃第17个威胁。
- 用户确认的 primary target: 仅用于 trace、风险解释与 revision evidence anchor；不表示单目标安全保证，切换不得 reset 其他 lifecycle。
- 新增盲区: BL-39 priority matrix；BL-40 capacity execution；BL-41 speed action；BL-42 primary hysteresis。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-13 · Degraded/unknown observation

- 专家: structural invalidity 与 quality degradation 必须分开；前者拒绝整个 cycle 且不改变 lifecycle state，后者有限期保守传播。
- 新手: 只把 `degraded=true` 写进 trace 没有安全效果；必须改变 uncertainty envelope、release guard 与 planning status。
- 悲观: 无限 coasting 会追踪 ghost target；立即删除又丢失真实 duty，因此需要 age/uncertainty hard limit。
- 默认最简版失效: 当前 adapter 对超龄 track 直接拒绝；Mid 只把 degraded 写入 target prediction；covariance 不影响 clearance/risk/release，没有 coasting uncertainty growth。[R1]
- 用户确认的 structural-invalid contract: NaN/Inf、frame/unit、timestamp、covariance 或 geometry 结构错误→PlannerInput 拒绝、lifecycle 不更新、显式 INVALID_OBSERVATION；不得当 clear 或 nominal fallback。
- 用户确认的 quality phases: VALID→DEGRADED→COASTING→UNUSABLE。DEGRADED/COASTING 保留 locked facts、扩大 uncertainty margin、禁止 release；COASTING 有限期预测；UNUSABLE 输出 OBSERVATION_LOST，不伪造 Mid-MPC SUCCESS。
- 用户确认的 low-speed semantics: COG invalid 不等于 target invalid；未 commit 输出 UNKNOWN_ROLE，已 commit 保持 locked role，禁止据此 release。
- 用户确认的 ownership: UNUSABLE 后控制权处理属于 adapter/runtime contract，L0 不偷偷实现 fallback。
- 新增盲区: BL-43 covariance margin；BL-44 runtime behavior；BL-45 coasting model；BL-46 unknown capacity。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-14 · L0→L1 immutable handoff

- 专家: stateful decision module 的基础不是普通 method call，而是幂等、原子、单调时间与显式 epoch/reset。
- 新手: `update(PlannerInput)->dict` 看似省事，却泄漏 route/ENC/execution contract，并允许 L1 修改 decision facts。
- 悲观: planner retry 可重复 commit；输入中途异常可让半数 target transition 后污染 state；必须 tentative-compute 后 atomic commit。
- 默认最简版失效: 当前 facade 在一次 solve 内直接 mutate 多个 dict/set，再装配 problem；没有 cycle identity、transaction 或 immutable decision seam。[R1]
- 用户确认的 interface: `EncounterLifecycle.step(EncounterCycle)->EncounterDecisionSnapshot`。Cycle 包含 session epoch、cycle identity、sim time、immutable observations、ownship maneuverability facts、Planner ODD profile identity；Snapshot 包含全部 per-target facts、aggregate directive、conflict/capacity/health status 与本周期 transition events。
- 用户确认的 L1 seam: `PlannerInput + EncounterDecisionSnapshot + LOS route reference -> MidMpcProblem`。Snapshot 不含 row index、horizon steps、CasADi、MidMpcProblem、IPOPT、LOS/ENC、deadline/fallback。
- 用户确认的 time/idempotency: 业务参数只用 seconds/meters/radians；sim time monotonic；same cycle+input retry 幂等；rewind 显式 reset；large gap 产生 evidence。
- 用户确认的 transaction: validate all→tentative next state→snapshot/evidence→atomic commit；异常不改变旧状态。
- 用户确认的 reset: `reset(session_epoch,reason)` 清除 active states、timers、commitments、tombstones、primary hysteresis、history，并产出 reset evidence。
- 新增盲区: BL-47 cycle identity；BL-48 reset authority；BL-49 gap policy；BL-50 schema mapping。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-15 · Lifecycle observability

- 专家: current state 与 transition evidence 必须分开；只看当前字符串无法审计因果。
- 新手: 把所有字段直接塞进自由格式 `algorithm_details` 会迅速产生字段 drift，且 integration/UI 反向侵入 lifecycle。
- 悲观: 保存无限完整历史会拖垮长仿真；typed evidence 需要 bounded in-memory retention 与独立 event sink。
- 默认最简版失效: 当前 trace 只给 instantaneous encounter、effective intent、policy_committed 与 aggregate side；没有 phase/generation/reason/commit/release/rearm/conflict provenance。[R1]
- 用户确认的 evidence: 每周期输出完整 per-target snapshot 与 transition events。Snapshot 同时保留 instantaneous classification 和 locked encounter/role，并含 health、risk/clearance、action/side、baseline/committed course、alteration achievement、release/rearm、priority、NLP inclusion/reason。
- 用户确认的 event envelope: event/session/cycle/time/target identity、from/to phase、stable reason code、trigger values、profile identity/hash、commitment before/after。Reason 覆盖 risk entry、urgent、role lock、substantial action、Rule17、past-clear、rearm、coasting/generation、multi-conflict/capacity、reset。
- 用户确认的 mapping: Lifecycle 只产 typed evidence；integration trace mapper 写入 `PlannerTrace.algorithm_details["encounter_lifecycle"]`。缺失值 null，禁止 NaN/Inf；trace 保存 current+cycle events，长期历史交 event sink，adapter 只保留 bounded ring。
- 验收可解释问题: why turn/hold/recover/side/stand-on act/release/rearm、哪些目标未入 NLP、当前 trajectory 对应哪个 locked commitment。
- 新增盲区: BL-51 schema version；BL-52 retention/sink；BL-53 profile hash；BL-54 GUI projection。
- 用户确认: 2026-08-11，确认。未形成最终 VR；待 Step4/Step5 裁决。

#### DP-16 · L0/L1 acceptance matrix

- 专家: lifecycle state、L0→L1 mapping、real-IPOPT closed-loop、runtime regression 必须分层；单个大场景无法定位失败层。
- 新手: Playground 没碰撞不能证明 role、side、release、rearm 或 substantial action 正确。
- 悲观: planner/evaluator 若共享 classification logic 会自证正确；contract fixtures 应使用手工 geometry facts，closed-loop 再用独立 evaluator。
- 默认最简版失效: 现有固定种子五场景 G3 可证明 Ship0 safety evidence，但不能证明 5° 已移除、substantial action、OT 双侧态势选择、Rule17 escalation、generation/rearm、degraded uncertainty、atomic/idempotent handoff。[R1][R2]
- 用户确认的 Layer A: 毫秒级 lifecycle contract matrix 覆盖 HO、CS GW/SO、OT port/starboard mirror、overtaken、flicker、track loss/generation、rearm、degraded、reset/retry/atomicity。
- 用户确认的 Layer B: L0→L1 mapping 覆盖 substantial constraint persistence、absolute commitment non-accumulation、passing side、uncertainty/dynamic margin、physical-time row schedule、all-active inclusion、>16 capacity，以及 lifecycle core 不含 solver artifacts。
- 用户确认的 Layer C: public P1RunHarness real-IPOPT 覆盖 HO、CS GW、non-cooperative CS SO、OT mirrors、overtaken、multi-target conflict；断言 Ship0 raw G3/hard gate、actual hull clearance、no fallback、real solver traces、actual substantial action、actual passing side、release/recovery。Target-target collision 记录但不作为 Ship0 Mid-MPC failure。
- 用户确认的 Layer D: frozen parity、focused/full pytest、Ruff/format/diff、8010 real planner event；event 必须显示 mid_mpc_ipopt、solver executed、typed lifecycle evidence、80×15s real trajectory、无 SB-MPC identity residue。
- 新增盲区: BL-55 non-cooperative fixture；BL-56 actual substantial metric；BL-57 dynamic/evaluator dual evidence；BL-58 mirrored/conflict fixtures。
- 用户确认: 2026-08-11，确认。Step2 DP-01..DP-16 已逐项 grilling；未形成最终 VR/ALT/TS，等待 Step3 深调证据。

### Step3 · Batch-1 基础规则、分类、风险进入与 lock 证据  [2026-08-11]

- 覆盖盲区: BL-01/02/07/10/11/12/13/16/17/18/19/20/21/22/23/24。
- 规则证据: Rule 13 不指定 OT passing side；Rule 8/16 不给 numeric substantial angle、TCPA 或 distance。`5°` 与 `30°` 都不是规则值；一次 absolute commitment 是工程实现，不是规则原文。[R14][R17]
- 分类证据: 112.5° OT boundary 有规则来源；HO nearly-reciprocal、crossing sector、speed tolerance 无统一标准值。边界/低速不确定性真实存在，具体阈值仍 implementation-specific。[R14][R17][R23]
- 风险证据: DCPA+TCPA 联合 entry、不同 entry/exit threshold hysteresis 有同行评审实现支撑；其 900m/270s/20s 属特定 Telemetron 仿真 tuning，不可直接搬入 Playground。[R5][R15][R18][R19]
- 动力学证据: action timing/release margin 应受双方尺度、relative speed 与本船 turning/stopping facts 影响；IMO manoeuvrability criteria 支持 length/dynamics scaling，但不定义 COLREG entry/release 数值。[R13][R16][R18][R19]
- 预测证据: instantaneous CV-CPA 是清晰 baseline，但对未来 own-route/target maneuver 有已知失效边界；标准没有强制 lifecycle entry 必须使用 nominal-route prediction。[R15][R20]
- lifecycle 证据: peer-reviewed Eriksen FSM、MASS M6、当前 Colav 结构均支持 per-target state/onset lock；跨来源不存在唯一“最小状态集合”，也没有 `entry_confirm_s`、target-maneuver reclassification 或 same-role timer merge 的标准答案。[R5][R22]
- 软件责任事实: Mid 当前未读取 evaluator profile，故“profile 直接反控 Planner”不成立；但 Planner 依赖 evaluator-owned `classify_geometry` 与隐藏 fallback，存在共同变更面。[R1][R21]
- 本批保留 UNKNOWN: numeric substantial angle；Playground action lead/clearance thresholds；entry confirmation seconds；target-maneuver reclassification threshold；same-role candidate merge；OT safe-clearance 时是否需要额外改向。
- 状态: 证据已写入 EV，盲区仍保持“调研中”；等待用户确认本批证据是否回答问题后，才能标闭环或 UNKNOWN accepted。
- 用户确认: 2026-08-11，Batch-1 证据充分；BL-01/02/07/10/11/12/13/16/17/18/19/20/21/22/23/24 标证据闭环，其中未有标准数值/唯一算法者保留 UNKNOWN 进入 Step4 ODD 裁决。

### Step3 · Batch-2 release、Rule17 与 multi-target 证据  [2026-08-11]

- 覆盖盲区: BL-03/04/06/25/26/27/28/29/30/31/32/33/39/40/41/42/55/57/58。
- release 证据: Rule 8/13 要求 safe passing、持续检查至 finally past and clear，但不给固定距离/时间。动态 domain 研究支持双方尺度、速度与 maneuverability 进入 guard；没有通用 past-clear 数值。[R14][R25][R12]
- recovery 证据: nominal route 与 collision-avoidance behavior 可分层，receding horizon 在恢复期间继续评估；没有标准化 PAST_CLEAR→recovery handoff 或 sudden-target horizon。[R26][R5]
- Rule17 证据: MAY_ACT 与 MUST_ACT 的法律强度不同；appropriate action 可由 Rule8/16 的及时、明显、有效和 safe-passing 结果判断。target-alone insufficiency 可用 reachable-set/NL-VO 或 tcrit 近似，但无唯一法律认可算法。[R14][R27][R28][R29]
- Rule17(c) 证据: 条文只限制 17(a)(ii) crossing action，且带 `if circumstances admit`；未提供与第三目标冲突的 priority matrix。[R14][R5]
- multi-target 证据: Rule2/8 要求考虑全部危险且不得制造新 close quarters；论文使用 per-target states/VO 并同时筛除任一 target conflict。不存在任意几何下的统一规则优先矩阵。[R5][R31][R32]
- passing/revision 证据: 实际路径几何/交点顺序比 initial turn sign 更能证明 passing side；Rule8 允许根据效果复核后纠正，但没有 discrete revision 的门槛/次数标准。[R14][R30]
- capacity/primary 项目事实: core 明确 max 16 并可 reject，facade 先 `[:16]` 静默截断；现有 no-fallback tests 没覆盖 capacity。Primary target 是工程解释概念；MASS 提供 sample/score hysteresis precedent，参数不可直接迁移。[R1][R2][R33]
- speed action 证据: Rule8(e) 必要时要求减速/停车；当前 Mid speed floor=0.25m/s 且无 speed commitment lifecycle。[R14][R1]
- fixture 事实: crossing-stand-on 已是 deterministic non-cooperative target 基座，但未断言 Rule17 transitions；当前无 OT mirrored lifecycle pair、无 MANEUVER_CONFLICT fixture。Imazu/多船论文提供场景库先例，不定义最小 fixture 集。[R2][R31][R32]
- fixed 50m 证据: evaluator 50m 是项目 acceptance constant，不是 IMO/COLREG safety value；dynamic domain 与固定 50m gate 测量不同命题，数值关系 UNKNOWN。[R1][R13][R25]
- 状态: 证据已写入 EV；本批盲区保持“调研中”，等待用户确认。
- 用户确认: 2026-08-11，Batch-2 证据充分；覆盖盲区标证据闭环，缺少标准数值、唯一 proxy、priority matrix、capacity runtime policy 者保留 UNKNOWN 进入 Step4。

### Step4 · DP-01 Encounter Lifecycle module 责任范围（推荐草案） [2026-08-11]

- 初步推荐: 建立纯 Python、stateful、solver-agnostic 的 `EncounterLifecycle` 深模块。唯一拥有逐目标时间状态、lock/hysteresis、risk phase、commitment/action/side、Rule17 escalation、release/rearm、observation-health phase、aggregate directive/conflict/capacity status、atomic step/reset 与 typed transition evidence。[R1][R3][R4][R22][R40]
- 输入边界: 消费 immutable `EncounterCycle` 与 planner-neutral pairwise facts；不拥有 sensor/tracker association。几何分类权威的具体 seam 留 DP-02 裁决。
- 输出边界: 只产 immutable `EncounterDecisionSnapshot`；不产 `MidMpcProblem`、row schedule、CasADi/IPOPT variables 或 executable command。
- 保留责任: L1 Problem Assembler 负责 `PlannerInput + snapshot + LOS reference -> MidMpcProblem`；pure IPOPT core 只解数学问题；CustomMPCAdapter 负责 schedule/deadline/error/no-fallback、触发 reset 与 trace mapping；L4 acceptance 独立验证 numerical/swept-CPA/COLREG execution quality。[R3][R4][R21]
- 证据链: 当前 facade 同时 mutation policy/release/LOS/assembler/solver，失败 retry 无 transaction；七层设计和 MASS pure seams 均支持决策与装配/求解分离；protocol evaluator 与 planner authority 应分离。[R1][R3][R4][R21][R40]
- 备选 A: 仅把 `_target_decisions` 拆成若干 facade helper。弃用草案理由: mutable dict/set、reset、evidence、retry transaction 与 multi-target aggregate 仍散在 facade，deletion test 不成立。
- 备选 B: 把 LOS、problem assembly、IPOPT 调用一起移入 lifecycle。弃用草案理由: module 过宽，业务状态与数学模型/solver artifacts 耦合，无法独立毫秒级 contract test。
- 备选 C: 直接复用 evaluator `PairwiseColregFSM/classify_geometry` 作为 lifecycle authority。弃用草案理由: planner/evaluator 共同变更面形成自评耦合；DP-02 尚需确定 planner-neutral geometry seam。[R1][R21]
- 实现风险: 中。风险源为新旧 facade 双状态、snapshot 过宽、assembler 重复解释 intent。约束为 lifecycle 成为唯一 state owner，assembler 只做显式 mapping，迁移期禁止双写。
- 失效边界: tracker 身份错误、输入 pairwise facts 错误、IPOPT infeasible、L4 执行跟踪失败不由 lifecycle 修复；必须通过 health/conflict/status/evidence 显式暴露并交给对应 owner。
- 验证需求: 无 solver/CasADi import 的 dependency test；逐目标 FSM contract matrix；same-cycle retry 幂等；solve exception 不污染 state；reset epoch/reason；snapshot immutability/JSON finite；facade 删除旧 commitment containers 后五类 closed-loop + multiship 复跑。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-16 L0/L1 acceptance matrix（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-15 typed schema、version/retention/provenance与三个弃用方向；写入 VR-15、ALT-43..45。
- 初步推荐: 四层acceptance逐层定位失败；A/B使用手工/独立facts避免planner/evaluator自证，C用public P1RunHarness+real IPOPT证明closed-loop，D做parity/runtime/regression。任何层失败不得用fallback、scenario special case或threshold weakening掩盖。[R2][R21][R30][R32]
- Layer A lifecycle contract: HO、CS GW/SO、OT port/starboard mirror、overtaken、boundary flicker、Rule13 doubt、Rule17 cooperative/non-cooperative MAY/MUST、past-clear/rearm、track loss/generation/discontinuity、degraded/coasting/UNUSABLE、multi-conflict、capacity、reset/retry/atomicity。毫秒级，不import solver/evaluator verdict。
- Layer B L0→L1 mapping: absolute baseline commitment不累加；minimum action持续至actual achievement；role/side/avoid-ahead/Rule17 constraints；dynamic/uncertainty margin；physical-time row schedule；all required targets inclusion；>16显式failure；Snapshot无solver artifacts。
- Layer C real-IPOPT closed loop: HO、CS give-way、cooperative与non-cooperative CS stand-on、OT port/starboard mirrors、overtaken、multi-target maneuver conflict。每场断言Ship0 raw G3+evaluator hard gate、actual hull clearance、no fallback、real solver statuses、actual substantial action、actual passing geometry、release/recovery与typed lifecycle sequence。
- actual action evidence: 从commit baseline到achievement/past-clear窗口计算真实COG/SOG alteration、持续时间、passing-side geometry与clearance improvement；不能只断言selected command、5°、first control sign或constraint activated。[R30][R42][R45]
- independent evidence: Planner ODD substantial/dynamic release thresholds与Evaluator 50m/apparent profile分开；Evaluator只看realized trajectory。Target-target collision单独记global evidence，Ship0 Mid-MPC不控制目标船，不能混成Ship0 failure，也不能隐藏。[R21][R42]
- Layer D regression/runtime: frozen C++ parity corpus全部保持；focused/full pytest、Ruff/format/diff；registry/capability只在证据通过后更新；8010 real planner event显示`mid_mpc_ipopt`、real IPOPT、typed lifecycle、80×15s真实trajectory、无SB-MPC identity residue；GUI Planner/Evaluator来源分离。
- gate semantics: Layer A/B必须全绿才跑昂贵C；C全部指定场景通过才提升capability；D full suite与live event完成才可合并。Focused tests不能替代full suite，G3不能表述为法律认证或全船全局安全。
- 备选 A: 只看Playground“没碰撞”/G3 PASS。弃用草案理由: 无法证明role、side、substantial action、Rule17、release/rearm或atomic contract正确。
- 备选 B: 只做unit/fixture tests，不跑real IPOPT closed-loop与8010。弃用草案理由: 无法证明L0→L1→solver→Ship执行链、真实轨迹和GUI证据。
- 备选 C: planner与evaluator共享expected label/threshold，失败时启用fallback、调场景或降低50m。弃用草案理由: 自证、阈值作弊和隐藏能力边界。
- 实现风险: 中高。成本主要来自场景运行时间、mirrored fixtures、非合作Rule17和实际trajectory metrics；但分层可把调试成本前移到毫秒级A/B。
- 失效边界: 固定seed Playground PASS只证明该ODD/场景/Ship0证据；不证明任意多船、传感器实船、MASS ROS2/GNC、法律认证或target-target全局安全。
- 验证需求: acceptance matrix本身成为tracked artifact；每项有test ID、owner、evidence field、pass/fail boundary；最终记录完整命令、测试数、耗时、live session/solve event和任何残余UNKNOWN。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。DP-16确认后Step4才完成，随后暂停等待Step5授权。
- 用户确认: 2026-08-11，采纳四层acceptance与三个弃用方向；写入VR-16、ALT-46..48。

### Step4 · 完整性门 [2026-08-11]

- DP-01..DP-16均已逐项展示推荐、证据链、弃用理由、实现风险、失效边界与验证需求，并获用户确认。
- TD-01 readiness: observation(DP-04)✓；classification(DP-05)✓；risk(DP-06)✓；lock(DP-07)✓；intent(DP-08)✓；Rule17(DP-09)✓；release(DP-10)✓；rearm/identity(DP-11)✓；multi-target(DP-12)✓；degraded(DP-13)✓；handoff(DP-14)✓；evidence(DP-15)✓。
- 所有Step3 UNKNOWN已进入对应Planner ODD/engineering recommendation，未伪装成COLREG/IMO标准数值；未发现`DECOMPOSITION_INCOMPLETE`。
- Step4 gate通过。VR-01..VR-16与ALT-01..ALT-48为Step4 final推荐；仍须Step5 DESIGN-IT-TWICE逐张决策卡确认后，才能进入Step6方案包。
- 状态: 暂停，等待用户授权Step5。

### Step5 · DESIGN-IT-TWICE 对比对象选择 [2026-08-11]

- 用户已授权进入Step5。
- CARD-01 `L0 module architecture & transaction`: 覆盖DP-01/02/03/14。比较deep stateful module、assembler-embedded engine、event-sourced/actor design；必须覆盖geometry authority、state ownership、atomic/idempotent handoff、solver failure boundary。
- CARD-02 `Observation identity & degraded tracking`: 覆盖DP-04/11/13。比较tracker-authoritative rich contract、adapter-synthesized compatibility contract、lifecycle-owned tracking state；必须覆盖generation、coasting、covariance、reacquisition、UNUSABLE控制权。
- CARD-03 `Pairwise COLREG decision lifecycle`: 覆盖DP-05/06/07/08/09/10。比较orthogonal deterministic FSM、hierarchical statechart、reactive risk-scoring/commitment policy；必须覆盖classification、risk entry、lock、substantial action、Rule17、release/rearm boundary。
- CARD-04 `Multi-target maneuver resolution`: 覆盖DP-12。比较constraint-set aggregation+single NLP、multi-mode candidate enumeration+多次solve、sequential priority arbitration；必须覆盖mandatory/conditional/preference、course conflict、speed/stop、capacity、primary semantics。
- CARD-05 `Evidence, compatibility & acceptance`: 覆盖DP-15/16。比较typed schema+bounded/live sink+layered gates、event-sourced audit as source-of-truth、trace-only scenario acceptance；必须覆盖schema version、profile provenance、retention、GUI、actual trajectory、real-IPOPT/8010/full regression。
- 低风险跳过候选: 无。原因: DP已被合并为五个技术整体；每个整体均影响控制行为、failure semantics或最终可审计性。是否仍指定CARD-05等为低风险直接采纳，必须由用户决定。
- 推荐执行顺序: CARD-01→02→03→04→05；每张卡2-3个完整自洽方案、七维对比，逐张确认后才写Step5 final VR/ALT。
- 状态: 等待用户确认五张卡范围与“无低风险跳过”。

### Step5 · CARD-01 L0 module architecture & transaction（决策卡草案） [2026-08-11]

- 用户确认: 五张CARD范围、顺序与无低风险跳过。

| 维度 | 方案A: Deep Transactional Lifecycle | 方案B: Assembler-Embedded Transaction Engine | 方案C: Event-Sourced Per-Target Actors |
|---|---|---|---|
| 来源 | 七层pure seam[R3][R4]；per-target FSM/solve-cycle freeze[R9][R10][R22]；职责分离[R21]；当前mutation缺口[R1][R40] | 当前facade同对象持有LOS/state/assembly/solve的project precedent[R1][R40]；FSM/onset lock[R5][R22] | per-target FSM[R5][R9]；typed events/schema[R42][R43]；transaction缺口[R40]；无来源要求本项目actor/event sourcing |
| 工程验证 | 部件有MASS/论文/当前项目验证；完整epoch+hash+atomic模块尚未real-IPOPT验证 | 最接近当前实现，迁移短；完整clone→solve→commit transaction尚未验证 | event replay/actor是通用工程模式；当前单进程Colav无落地证据 |
| 技术分解 | DP-01/02/03/14完整：neutral geometry→single state owner→frozen Cycle/Snapshot→L1 Assembler→solver；decision/execution分离 | 功能完整：single engine内geometry/FSM/assembly/solve；只在solver成功后提交state+solution，但消失独立L0 snapshot | 功能完整：geometry events→per-target actors→cycle barrier→commit marker→snapshot projector→solver execution event；另需journal/migration/compaction |
| 失效边界 | 错误identity/geometry会稳定锁错[SC-08]；in-memory atomic不等于crash durable；solver失败时decision/execution出现显式分叉 | IPOPT失败使world/rule state停在旧cycle；长solve锁阻塞新cycle/reset；GUI/L4无法在solve前看到decision[SC-09] | actor乱序/barrier timeout/journal损坏/投影不一致即fail-stop[SC-06/09]；I/O/replay侵入实时周期；仍不能修复错误facts |
| 实现风险 | 中高：新旧state切换、epoch/hash、snapshot cache；但边界少且failure可见 | 近期中、长期高：迁移小，但engine同时承受LOS/FSM/Assembler/IPOPT变化，solver反控rule state | 高：mailbox、ledger、journal、commit coordinator、projector、schema migration、crash recovery均为新增故障面 |
| 可测性 | 高：pure transition/invariant/retry/hash/reset/atomicity可脱离solver；再补real-IPOPT分叉测试[SC-01/07/09] | 中：可fake solver做transaction injection，但公开接口无法独立测L0；大量序列测试需route/problem/solver | 高但负担极高：replay/crash/order/dedup测试强，同时需额外journal/projection/migration/compaction矩阵 |
| 推荐度 | ★★★★★ | ★★★☆☆ | ★★☆☆☆ |

- 初步裁决推荐: 方案A。理由: 唯一同时保持Step4的L0/L1责任、decision与execution分离、独立可测、幂等atomic handoff；新增复杂度集中在一个同步deep module，适合当前单进程Playground。
- 方案B真实优势: migration短、problem/state成功事务一致、组件少。弃用草案理由: authoritative lifecycle被定义成“最后一次solver成功的world state”；IPOPT失败会阻止Rule17/commitment/time state前进，optimizer反控业务decision。
- 方案C真实优势: crash replay、审计和多进程扩展最强。弃用草案理由: 当前目标是单进程Mid算法验证；actor/journal不提升COLREG算法，且需要cycle commit coordinator后actor自治收益有限，成本与新failure modes过大。
- 运营取舍: 若未来明确要求跨进程热恢复、事故级完整replay和多个consumer共享同一lifecycle stream，可回炉方案C；当前不为假设需求预建。
- 状态: final。用户于2026-08-11确认采纳方案A、弃用B/C；写入VR-17、ALT-49..50。

### Step5 · CARD-02 Observation identity & degraded tracking（决策卡草案） [2026-08-11]

- 前项确认: CARD-01采纳Deep Transactional Lifecycle；本卡只裁决观测/track identity权威，不改变L0对encounter duty的唯一状态所有权。
- 当前项目事实: `TrackedObstacle`已有state/covariance/hull/observed_at/age/degraded，但仅以裸`target_id`标识；adapter在缺少`track_ages_s`时默认age=0。`GodTracker`每次重建当前快照；`KF`可输出预测track，但下游tuple没有UPDATED/COASTING/TERMINATED或generation语义。因此当前L0无法可靠区分fresh observation、tracker prediction、暂时丢失、ID reuse。[R34][R40]

| 维度 | 方案A: Tracker-Authoritative Rich Contract | 方案B: Adapter-Synthesized Compatibility Contract | 方案C: Lifecycle-Owned Tracking State |
|---|---|---|---|
| 来源 | 当前tracker已拥有association/state/covariance[R34]；IMO radar/AIS要求track状态/更新时间可见[R35]；ASTERIX提供track status/quality/identity precedent[R38] | 当前`do_list + track_ages_s`和adapter validation为直接project precedent[R34][R40]；DP-11允许显式legacy compatibility path | 当前KF的CV prediction/covariance模型可复用概念[R34][R37]；无七层/MASS/项目证据要求COLREG lifecycle拥有tracking |
| 工程验证 | state/covariance已有实现；新增generation/status/provenance contract尚未在God/KF与real-IPOPT链验证 | 最接近现有public adapter，God场景迁移短；仅靠tuple推断generation/coasting未被证明可靠 | 单模块可在synthetic detections上闭环测试；复制association/KF后无现有runtime验证 |
| 技术分解 | Tracker输出immutable `TrackSnapshot(key=id+generation,status,state,covariance,hull,observed_at,source,quality)`；Observation Builder验证finite/PSD/age/COG validity并冻结Cycle；Lifecycle只消费facts、保留episode/duty；tracker明确UPDATED/COASTING/TERMINATED/reacquired | 保留旧tuple；Compatibility Adapter以per-ID cache、missing interval、continuity gate和可选metadata合成generation/age/health；缺字段标`LEGACY_UNKNOWN`，不得默认fresh；无法证明时UNUSABLE | Lifecycle内新增TrackMemory：接收raw detections/legacy tracks，自行association、generation、CV/KF coast、covariance growth、reacquisition/termination；随后同事务推进COLREG FSM |
| 失效边界 | tracker错误association会成为稳定但错误identity；合同只能暴露quality/provenance，不能自行修复；tracker不发termination会保留ghost track | 同ID消失/重现与ID reuse不可判定；KF predicted tuple与fresh update同形；continuity heuristic可能错误继承或错误换代；严格UNKNOWN会使旧tracker fail-stop | association/model错误与COLREG状态共享故障域；错误track update可同时污染identity、risk、release；同一sensor事实可能与其他算法产生不同track truth |
| 实现风险 | 中高：改God/KF output、Ship/adapter DTO与tests；但责任边界稳定，migration可逐tracker完成 | 近期中、长期高：少改tracker，但adapter成为隐式第二tracker；source特判、cache/reset/time-gap逻辑持续增长 | 高：重写/复制tracker、data association、covariance、termination；Lifecycle由deep decision module膨胀成tracking+decision系统 |
| 可测性 | 高：tracker contract、Observation Builder、health mapping、Lifecycle分别测试；generation/reacquire/coast/UNUSABLE可构造确定序列 | 中：可测heuristic，但无法从输入证明ground truth；大量测试只能确认“推断一致”，不能确认identity正确 | 中高：synthetic序列可端到端测，但failure定位跨association/estimation/COLREG；需重复KF统计测试 |
| 推荐度 | ★★★★★ | ★★★☆☆ | ★★☆☆☆ |

- 初步裁决推荐: 方案A。identity/age/status由最接近传感器和association事实的Tracker权威产生；Observation Builder只验证、标准化、派生COG validity与health，不猜generation；Lifecycle只拥有encounter episode/duty。
- 方案B真实优势: 旧tracker与adapter改动最少，可作为具名、限时migration bridge。弃用为最终架构的理由: 当前tuple信息不足，无法可靠区分fresh/coasting或same-ID reuse；cache heuristics会形成第二套tracker。若保留bridge，缺失字段必须`LEGACY_UNKNOWN/UNUSABLE`，禁止age=0。
- 方案C真实优势: track identity与encounter state可一次atomic transaction，单算法自包含。弃用草案理由: 复制现有tracking职责，扩大故障域；不同COLAV算法可能基于不同track truth，违反planner-neutral L0输入目标。
- UNUSABLE控制权（三方案共同硬约束）: 缺失/非finite/超龄/identity conflict/uncertainty超预算且无法形成安全约束时，Observation Builder/Lifecycle输出typed failure；adapter不调用IPOPT、不继续cached plan。真实船最低风险控制仍属上层监督，不由Mid伪装实现。
- 状态: final。用户于2026-08-11确认采纳方案A、弃用B/C；写入VR-18、ALT-51..52。方案B只允许作为具名、限时migration bridge，缺字段不得伪造fresh。

### Step5 · CARD-03 Pairwise COLREG decision lifecycle（决策卡草案） [2026-08-11]

- 前项确认: CARD-02采纳Tracker-Authoritative Rich Contract。本卡消费已冻结、有效性明确的pairwise observations；不重新承担tracking/association。
- 当前项目事实: facade以三个裸容器保存policy/course/released ID；每周期instant classification后直接commit，minimum-alteration只在`newly_committed`首轮启用；HO/CS按`signed_tcpa<=0`释放，OT按固定距离释放；stand-on永久HOLD；缺少candidate confirmation、Rule17 escalation、achievement/revision、generation/rearm与typed transition。[R1][R2]

| 维度 | 方案A: Orthogonal Deterministic FSM | 方案B: Hierarchical Statechart | 方案C: Reactive Risk-Scoring + Commitment Policy |
|---|---|---|---|
| 来源 | per-target FSM与solve-cycle freeze有论文/MASS证据[R5][R9][R10][R22]；Step4已确认orthogonal typed facts | evaluator/MASS已有显式FSM precedent[R1][R22]；hierarchy/parallel regions属通用statechart方法，但当前项目无engine precedent | 当前facade已有instant policy+latched commitment[R1]；MASS risk rank/score hysteresis提供工程precedent[R33]；BC-MPC使用连续risk/cost[R5] |
| 工程验证 | 单项classification/commitment/closed-loop已有project evidence；完整Rule17/release/rearm正交FSM尚未实现 | 图式transition适合review/可视化；项目无statechart runtime、serialization或real-IPOPT集成证据 | risk ranking与连续cost已被使用；用score统一法律duty、Rule17、release尚无验证 |
| 技术分解 | `advance(previous, observation, profile)->state+decision+events`；按health/identity→classification→risk→confirmation/lock→action/side→Rule17→achievement/past-clear/rearm固定顺序；state以phase/locked encounter/role/Rule17/action/side/episode正交字段表达；每cycle冻结 | 一个event-driven composite chart；顶层OPERATIONAL/DEGRADED/COASTING/UNUSABLE，内部GiveWay/StandOn/OT层级与parallel Risk/Action/Rule17/Release regions；entry/exit/history动作产snapshot/events；需statechart engine、event queue、guard priority | 每cycle为HOLD/GIVE_WAY(port/starboard)/speed/STOP等候选计算rule+risk+clearance+reachability score；confirmation与inertia latch承诺；Rule17 evidence改变候选eligibility/mandatory权重；release score+持续时间解锁；输出score breakdown |
| 失效边界 | 错误facts/profile会确定性锁错；正交字段需invariant validator防非法组合；显式UNKNOWN/conflict，不能创造可行maneuver | event ordering、guard priority、deep-history恢复和parallel region冲突可能产生隐式行为；图看似完整但跨区域invariant仍需额外验证 | 权重/归一化变化可悄然改写COLREG duty；阈值附近score翻转；“最高分”不等于法律义务或共同可行；解释容易退化为事后理由 |
| 实现风险 | 中高：transition table、invariants、timers、episode migration；但无外部framework且pure | 高：引入/自建engine、事件语义、并行区域合并、serialization/debug tooling；状态迁移成本高 | 中：可复用risk calculations；但calibration与跨场景权重耦合高，Rule17/release难保证单调语义 |
| 可测性 | 高：每条guard、same-cycle retry、时间尺度、边界抖动、mirror、Rule17、release/rearm均可table/property test；无需solver | 高但矩阵大：transition coverage/visual graph强；还需event ordering/history/parallel race tests | 中：适合parameter sweep/fuzz/metamorphic tests；难证明未测试权重组合下duty不被覆盖，失败定位较差 |
| 推荐度 | ★★★★★ | ★★★☆☆ | ★★★☆☆ |

- 初步裁决推荐: 方案A。它直接落实已确认的“规则事实正交、cycle内冻结、episode有记忆”，不引入runtime framework；transition顺序和invariants可成为L0 contract。
- 方案B真实优势: 复杂Rule17、degraded、rearm路径可视化，entry/exit/history适合形式化transition coverage。弃用草案理由: 本问题核心是多组正交事实，不是单一深层父子层级；parallel statechart最终仍需A式invariant/merge规则，同时新增event ordering与engine依赖。
- 方案C真实优势: 对连续风险、噪声与OT双侧选择自然，便于未来multi-target action ranking。弃用为pairwise lifecycle authority的理由: score适合DP-12候选排序，不适合决定Rule13 duty是否存在、Rule17法律阶段或release事实；权重调参会隐式改规则状态。
- substantial action硬约束: A不内置5°或30°常数；profile根据船体、机动能力、风险时间、净空和可达性形成一次baseline-relative commitment，持续至真实achievement。OT在commit前评估port/starboard，commit后锁定；修订必须离散、有reason/evidence。
- 状态: final。用户于2026-08-11确认采纳方案A、弃用B/C；写入VR-19、ALT-53..54。Risk scoring保留为CARD-04候选排序技术，不作为pairwise规则状态权威。

### Step5 · CARD-04 Multi-target maneuver resolution（决策卡草案） [2026-08-11]

- 前项确认: CARD-03采纳Orthogonal Deterministic FSM。本卡只在全部pairwise states已推进并冻结后聚合；primary切换不得反向重置pairwise lifecycle。
- 当前项目事实: facade先按TCPA/DCPA/range排序并静默`[:16]`，随后`any mandatory starboard wins`，否则复制首个give-way side；core对全部选中targets施加CPA，但`preferred_side/starboard_asymmetry/minimum_alteration/row_schedule`均为problem级单一值，不表达per-target direction corridor。故现状既可能丢第17个active threat，也可能把相反pairwise要求压成一个sign。[R1][R2]

| 维度 | 方案A: Constraint-Set Aggregation + Single NLP | 方案B: Multi-Mode Enumeration + Multiple NLP Solves | 方案C: Sequential Priority Arbitration |
|---|---|---|---|
| 来源 | Rule2/8要求动作不制造另一close-quarters；论文按全部目标联合约束/筛选[R14][R31][R32]；当前Mid core本身支持一个NLP含多targets[R1] | scenario-based MPC与离散mode评估提供技术precedent[R20]；当前Mid可构造不同global-side problem，但无multi-solve runtime contract | 当前facade排序/首策略和MASS primary hysteresis为project precedent[R1][R33]；部分论文采用rule priority[R5] |
| 工程验证 | CPA multi-target与3-target closed-loop已有验证；完整course-corridor/conflict/capacity directive及frozen-core representability尚未验证 | 每mode可复用现有IPOPT/parity；无deadline、mode consistency、commit-before-solve或多次cold-start证据 | 实现最接近现状且计算成本最低；现有CCTA场景通过不证明相反义务下aggregate正确 |
| 技术分解 | 全pairwise outputs→typed mandatory/conditional/locked/preference约束集合→基于maneuverability的course corridor交集与speed/STOP可行性→`AggregateDirective(required targets,corridors,speed bounds,conflict,capacity,primary evidence)`→L1 representability gate→单次all-target NLP；preference只排序，不覆盖hard facts | L0输出legal mode set；L1为port/starboard/course-hold/speed-reduce/STOP组合建立多个all-target problems，逐个IPOPT；acceptance gate比较feasible trajectories后选mode；若selected mode回写commitment则需两阶段L0 transaction | 以MUST/COMMITTED/risk rank选primary，生成其动作；对其余targets做safety veto并依次修正course/speed；冲突时低priority duty延后或切speed；最终单次NLP跟踪仲裁结果 |
| 失效边界 | corridor交集为空、required>16或当前core无法表达per-target constraint时显式`MANEUVER_CONFLICT/CAPACITY_EXCEEDED/CORE_CAPABILITY_MISMATCH`；不能把偏好升级成法律义务 | 多个mode都infeasible或超deadline；不同solve numerical noise改变mode；solver结果若决定commitment，违反CARD-01 decision/execution分离；mode组合随targets增长 | priority不等于共同可行；后处理veto可能反复推翻前一动作；低priority target仍可进入close quarters；若迭代到共同约束闭包，最终退化为方案A |
| 实现风险 | 高：typed constraint algebra、angle wrap/corridor intersection、speed-course coupling、core capability gate；但只solve一次且failure可见 | 很高：N倍cold-start IPOPT、deadline预算、结果归一化、mode explosion、commit transaction重开 | 中：代码短、单solve；但行为/安全风险高，场景增加后priority special cases增长 |
| 可测性 | 高：纯aggregate contract可穷举相容/冲突/mirror/capacity；再用单次real-IPOPT验证mapping | 中高：每mode可测，但组合数、timeout/numerical tie与两阶段commit形成昂贵矩阵 | 中：priority unit tests简单；难证明未选目标安全，反例依赖闭环几何 |
| 推荐度 | ★★★★★ | ★★★☆☆ | ★★☆☆☆ |

- 初步裁决推荐: 方案A。L0先证明规则/承诺约束是否存在共同course/speed集合；L1只映射一个冻结AggregateDirective；IPOPT只解一个all-target数学问题，不决定规则duty。
- 方案B真实优势: 对OT未锁侧和非凸离散mode可直接利用trajectory feasibility，可能比解析corridor保守性低。弃用草案理由: 80×15s cold-start IPOPT多次求解显著放大deadline；更关键是若由solver胜者决定commitment，会破坏已确认CARD-01原子单向handoff。除非未来重开该裁决，不采用。
- 方案C真实优势: 迁移短、计算固定、primary解释直观。弃用草案理由: Rule2/8不允许“pairwise高优先级通过”替代对全部危险的联合复核；加入完整veto/修正后实质会重新实现方案A。
- frozen-core边界: 当前core只能表达一个global preferred side/common row schedule。L1不得把不可表达的per-target约束静默折叠；首版若AggregateDirective要求不同target-specific方向时显式`CORE_CAPABILITY_MISMATCH`。是否扩展pure MPC core属于Step6 implementation slice，不在L0中偷渡solver逻辑。
- capacity/primary硬约束: lifecycle处理全部tracks后才做capacity；所有MUST/COMMITTED/ACTION_CANDIDATE/active safety targets均required。required>16直接failure。Primary只用于GUI/evidence和稳定排序，不等于只保证该目标。
- 状态: final。用户于2026-08-11确认采纳方案A、弃用B/C；写入VR-20、ALT-55..56。当前core不可表达per-target direction时必须显式`CORE_CAPABILITY_MISMATCH`，不得折叠。

### Step5 · CARD-05 Evidence, compatibility & acceptance（决策卡草案） [2026-08-11]

- 前项确认: CARD-04采纳Constraint-Set Aggregation + Single NLP。本卡裁决如何证明L0/L1/Mid能力；evidence不得成为Planner decision authority。
- 当前项目事实: `PlannerTrace`外层有`schema_version=1.0`，但Mid细节仍散在自由格式`algorithm_details/target_predictions/constraints`；`SimulationSession.frames/events`内存无界，`planner_solved`只记录solve快照，无lifecycle transition事件。RunManifest已有canonical content hash，EvidenceWriter已有增量持久化基础；GUI同时展示planner/evaluator信息但缺少明确source/profile分界。[R40][R42][R44][R46]

| 维度 | 方案A: Typed Schema + Bounded/Live Sink + Layered Gates | 方案B: Event-Sourced Audit as Source of Truth | 方案C: Trace-Only Scenario Acceptance |
|---|---|---|---|
| 来源 | 当前PlannerTrace/RunManifest/EvidenceWriter提供直接基础[R40][R42]；schema/version/log stability有CNCF/OpenTelemetry precedent[R43][R46]；canonical hash有RFC precedent[R44] | typed events与现有session events提供append-log基础[R42][R43]；无需求或项目precedent把journal作为control state authority | 当前single/multiship closed-loop、capability registry与8010 trace即此模式[R2][R42] |
| 工程验证 | 外层schema、run manifest、persistence与场景测试均已运行；新增lifecycle子schema、bounded ring和四层gate尚未整体验证 | replay/audit是成熟通用模式；当前Colav无journal recovery、schema migration、projection或crash-consistency验证 | 已有G3与real-IPOPT场景证据，迁移成本最低；但这些证据未覆盖L0 transition contract、Rule17、identity/degraded和core mismatch |
| 技术分解 | immutable Snapshot/Event typed子schema（major/minor）→live bounded ring→incremental evidence sink；canonical Planner ODD/profile hash+build/run identity；GUI分栏Planner decision与Evaluator verdict；Acceptance A lifecycle contract、B L0→L1 mapping、C real-IPOPT closed-loop、D parity/full regression/8010 | 每个observation/transition/aggregate/problem/solve/control/evaluator结果写append journal；Lifecycle state、GUI与acceptance均从replay projection恢复；需sequence/commit marker/checkpoint/compaction/migration | 继续只在solve时写PlannerTrace；在`algorithm_details`添加少量字段；依赖现有scenario end metrics、capability tuple与人工8010观察判定PASS |
| 失效边界 | sink写失败标`EVIDENCE_INCOMPLETE`且不得伪装验收通过；live ring丢旧数据但durable sink保留；schema major不兼容显式拒绝；evidence failure不回滚decision | journal不可写/损坏/乱序会同时阻断authoritative state和控制；projection版本差异可能产生不同decision；I/O进入实时关键路径 | 字段缺失/重命名可静默；只有latest solve无法解释transition因果；session内存增长；Planner/Evaluator同标签可能形成自证；人工截图不可复现 |
| 实现风险 | 中：typed DTO、serializer、bounded buffer、sink/profile hash、GUI mapping和test matrix；复用现有基础 | 很高：重构CARD-01状态权威，引入journal transaction、replay、checkpoint、migration、recovery和operational tooling | 低实现、高认知风险：代码少，但能力声明容易超过证据，后续字段drift与回归定位成本高 |
| 可测性 | 高：schema golden/compatibility、retention、sink failure、profile hash、source separation；A/B快测后才跑昂贵C/D | 高但矩阵巨大：replay equivalence、crash points、duplicate/order、projection migration、compaction均需测 | 低至中：闭环结果可测；无法独立穷举lifecycle guards、atomic retry或schema consumer compatibility |
| 推荐度 | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ |

- 初步裁决推荐: 方案A。使用当前trace/persistence基础增加一个稳定typed lifecycle evidence seam；live observability与durable evidence分离；四层gate从纯L0到8010逐步增加成本。
- 方案B真实优势: 事故级完整replay、crash recovery和多consumer audit最强。弃用草案理由: 会把CARD-01已确认的同步in-memory lifecycle改成journal authority，控制路径受I/O与projection影响；当前Playground验证不需要此复杂度。
- 方案C真实优势: 不改基础设施，最快延续现有G3/8010流程。弃用草案理由: outcome trace不能证明decision contract；自由格式字段、无transition history和人工观察无法支撑本轮L0/L1深化。
- schema/retention裁决草案: 保留`PlannerTrace`外层兼容；新增versioned `lifecycle`子文档与typed transition events。minor只增optional字段；breaking change升major。Live ring固定上限；完整events增量写sink。Planner profile hash采用canonical resolved values，不含绝对路径；不得只记build hash。
- acceptance gate草案: Layer A/B全绿才运行C；C覆盖HO、CS-GW、CS-SO cooperative/non-cooperative、OT port/starboard mirror、overtaken、multi-target conflict，断言real IPOPT/no fallback/actual action+passing+clearance+Rule17+release；Layer D保持frozen C++ parity、full pytest/lint、capability更新与8010真实planner event。Target-target collision继续单独记录，不混成Ship0 failure或隐藏。
- UI证据草案: 明确标注`Planner interpretation/profile`与`Evaluator observation/profile`；显示80×15s真实IPOPT trajectory、lifecycle phase/reason、selected targets、aggregate conflict/capacity/core mismatch、solver identity/status。不得用Evaluator label填Planner缺失字段。
- 状态: final。用户于2026-08-11确认采纳方案A、弃用B/C；写入VR-21、ALT-57..58。

### Step5 · 完整性门 [2026-08-11]

- CARD-01 final: Deep Transactional Lifecycle（VR-17；ALT-49..50）。
- CARD-02 final: Tracker-Authoritative Rich Contract（VR-18；ALT-51..52）。
- CARD-03 final: Orthogonal Deterministic FSM（VR-19；ALT-53..54）。
- CARD-04 final: Constraint-Set Aggregation + Single NLP（VR-20；ALT-55..56）。
- CARD-05 final: Typed Schema + Bounded/Live Sink + Layered Gates（VR-21；ALT-57..58）。
- 五张关键决策卡均完成七维对比并逐张获用户确认；无低风险跳过项；VR-01..VR-21与ALT-01..ALT-58为当前final裁决。
- Step5 gate通过。当时尚未创建Step6 solution pack、尚未写TS、尚未标记“已交付to-spec”。状态暂停，等待用户明确授权进入Step6。

### Step4 · DP-15 Lifecycle observability（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-14 cycle identity、atomic step、solver failure分离与三个弃用方向；写入 VR-14、ALT-40..42。
- 初步推荐: Lifecycle只产typed `EncounterDecisionSnapshot`与`LifecycleTransitionEvent`；integration mapper序列化到`PlannerTrace.algorithm_details["encounter_lifecycle"]`。current snapshot与transition events分开，缺失值为null，禁止NaN/Inf。[R42][R43]
- schema envelope: lifecycle独立`schema_version`、`dataschema`/event type；每event含event_id、session epoch、cycle id/input hash、sim/observed time、target `(id,generation,episode)`、from/to、stable reason code、trigger values、profile identity/hash、commitment before/after。[R43]
- snapshot payload: per-target instantaneous/locked encounter+role、phase、health、risk/current/future clearance、action/side、baseline/commitment、achievement、release/rearm、priority、NLP inclusion/reason；aggregate action、primary、conflict/capacity/status；本cycle event references。
- version policy: semantic major/minor；同major只允许additive optional fields与reason-code扩展，consumer忽略unknown fields；rename/remove/type/meaning change必须new major/dataschema。Writer只产当前版，contract tests保留前一major reader fixture。[R43]
- retention ownership: Adapter只保留configurable bounded ring供live GUI/latest diagnostics；Session/EvidenceWriter拥有长期append-only event sink。Ring capacity/overflow policy显式配置并产`events_dropped_count`，不使用无界list，也不把GUI 60/500当evidence容量。[R42][R46]
- persistence: transition event在cycle成功后增量写JSONL，而非只在run finalize一次batch落盘；snapshot可按cycle采样/manifest关联。崩溃持久性/fsync等级作为execution profile参数，不塞进Lifecycle core。
- profile provenance: Planner ODD profile具`profile_id/schema_version`；对去除部署绝对路径后的normalized内容做RFC8785 canonicalization+SHA-256。Trace同时携profile hash、build identity hash，二者不混合。[R42][R44]
- GUI default: 明确标源`Planner Lifecycle`，显示primary target、phase、locked role、action/side、health、latest transition reason、conflict/capacity。完整trigger/profile/instantaneous-vs-locked facts放目标drill-down；Evaluator instantaneous COLREG badge保持独立来源，不互相覆盖。[R42]
- 备选 A: 继续把自由格式fields散放`algorithm_details`，无子schema/version。弃用草案理由: 字段drift、消费者无法区分缺失/旧版/语义变更。
- 备选 B: 内存保留全部历史，或只保留latest snapshot无event sink。弃用草案理由: 前者长run无界增长，后者无法审计why/when transition。
- 备选 C: 直接hash含绝对dependency path的resolved profile mapping，或只记录descriptor/build hash。弃用草案理由: 跨checkout不稳定，且不能单独证明Planner ODD参数身份。
- 实现风险: 中。风险来自schema演进、事件量、增量sink性能、GUI信息密度与当前PlannerTrace 1.0兼容。需保持mapper为唯一JSON boundary，Lifecycle不依赖GUI/OTel/CloudEvents库。
- 失效边界: 完整trace不证明算法正确；sink write失败也不能静默当solver成功证据。Observability failure应独立status，不修改decision facts。
- 验证需求: JSON schema/golden；null/finite；same-cycle retry不重复event；major/minor compatibility；unknown-field reader；stable cross-path profile hash；bounded long-run memory/overflow evidence；crash前已写transition；GUI source/phase/reason/conflict DOM；Evaluator badge独立。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-14 L0→L1 immutable handoff（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-13 health、UNUSABLE fail-stop、UNKNOWN_ROLE capacity与三个弃用方向；写入 VR-13、ALT-37..39。
- 初步推荐: authority seam保持`EncounterLifecycle.step(EncounterCycle)->EncounterDecisionSnapshot`；Cycle/Snapshot均frozen immutable。L1只消费`PlannerInput + Snapshot + LOS reference`装配`MidMpcProblem`，不得回写Lifecycle facts。[R3][R4][R40]
- cycle identity: `(session_epoch, cycle_id, input_hash)`。session epoch由Experiment/SimulationSession run identity产生；cycle id按成功采样周期单调；input hash覆盖normalized observation/profile identity，不覆盖部署绝对路径。same triple retry返回byte-equivalent snapshot且不重复transition。
- conflict semantics: same epoch/cycle_id但不同input_hash输出`CYCLE_ID_CONFLICT`；sim time倒退输出`TIME_REWIND_REQUIRES_RESET`。禁止把重复投递误作新cycle或普通hold。[R40][R41]
- atomic step: validate entire cycle→在私有copy计算全部per-target/aggregate next state与events→validate invariants/JSON-finite→一次替换authoritative state并返回snapshot。任一步异常旧state不变，禁止逐target边算边写。
- downstream failure: Lifecycle成功step得到的完整decision snapshot可以成为authoritative decision，即使后续Assembler/IPOPT失败；solver failure是独立execution evidence，不回滚已观测到的world/lifecycle transition。same-cycle retry复用同snapshot，因此不会丢`newly committed`语义或重复event；DP-08 persistent commitment保证重试仍带约束。
- time gap: 所有timer使用sim-time seconds。positive gap超过`max_cycle_gap_s`时不把整段gap当连续有效confirmation；输出`TIME_GAP`，按真实age进入DEGRADED/COASTING/UNUSABLE。若active duty无法由可用观测安全延续，则fail-stop，不自动reset或乐观release。数值属Planner ODD。[R40][R41]
- reset: `reset(session_epoch, reason)`清除per-target state、candidate timers、commitments、tombstones、primary hysteresis、snapshot cache；产生typed reset event。Web reset/replay创建new epoch；direct reset同样必须new epoch或显式reason，solve_id是否归零不再作为lifecycle identity。[R40]
- snapshot content: schema/profile identity；cycle/ownship facts；完整per-target instantaneous+locked facts、phase/health/risk/commit/release/rearm/priority/NLP inclusion reason；aggregate directive/conflict/capacity/primary；本cycle transition events。禁止row indices、horizon steps、CasADi/IPOPT objects、deadline/fallback policy。
- 备选 A: 继续由facade直接mutate多个dict/set后调用solver。弃用草案理由: partial mutation、retry非幂等、异常污染与职责混合。
- 备选 B: 只用sim_time或solve_id识别cycle，不做input hash/epoch。弃用草案理由: reset后ID复用、same-time不同输入和失败retry无法区分。
- 备选 C: solver成功才提交lifecycle，或solver失败回滚整个decision。弃用草案理由: world observation/规则decision被optimizer结果反向控制；retry会重复transition。正确分离是decision commit与execution status并列证据。
- 实现风险: 中高。风险来自session epoch传播、canonical input hash、snapshot cache、large-gap policy和当前adapter schedule契约。需先做public-seam contract tests再迁移facade。
- 失效边界: immutable handoff不保证solver可行或command可跟踪；只保证同一证据产生同一decision且状态不半更新。外部runtime若绕过epoch/cycle contract应INVALID_INPUT。
- 验证需求: same-cycle same-hash byte-equivalent；same-cycle diff-hash conflict；internal exception atomicity；downstream solver failure后retry不重复event；time rewind/reset；large gap不累计confirmation；new epoch清空；snapshot frozen/finite/schema-valid；Assembler无法修改；无solver artifacts dependency。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-13 Degraded/unknown observation（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-12 聚合顺序、priority、conflict/capacity与三个弃用方向；写入 VR-12、ALT-34..36。
- 初步推荐: observation health由finite/age/covariance/identity/track-status联合判定为`OBSERVED/DEGRADED/COASTING/UNUSABLE`，阈值来自Planner ODD；health与lifecycle duty正交，不能把数据差直接映射CLEAR。[R34][R35][R38]
- OBSERVED: 正常允许entry、achievement、revision、past-clear等双向transition。
- DEGRADED: 保留locked duty；允许基于保守margin维持/升级risk，但禁止仅凭degraded数据证明release、动作已达成或role降低。Covariance按profile confidence转成uncertainty margin，并记录assumption/confidence。[R39]
- COASTING: 沿用DP-11短期prediction、age与covariance growth；保留commitment，暂停需要fresh evidence的transition。超过coast timeout或uncertainty budget转UNUSABLE，不无限预测。[R36]
- UNUSABLE: 缺失/非finite/超龄/identity conflict/uncertainty超预算且无法形成安全约束。输出typed `OBSERVATION_UNUSABLE`/`PlanStatus.INVALID_INPUT`与source/reason；当前Playground strict-no-fallback语义为Session fail-stop，solver不执行，Ship不应用新控制。禁止返回HOLD/SUCCESS或缓存旧plan。[R40]
- control-authority boundary: Playground fail-stop只证明仿真拒绝无证据控制，不等价于真实船安全动作。真实MASS/GNC supervisory fallback/最低风险状态属于更高层，当前Mid移植不实现、不宣称。
- covariance margin: Gaussian/PSD且layout已知时可用`sqrt(chi2_2(confidence))*projected_sigma`形成位置margin；confidence/risk budget是Planner ODD。非Gaussian、未知cross-correlation或invalid covariance不得伪造置信域，降级或UNUSABLE。[R39]
- UNKNOWN_ROLE: 低速/边界目标仍参与collision risk、aggregate与NLP capacity。若approaching且clearance危险，作为`UNKNOWN_OBLIGATION` active threat占slot并添加无side的安全约束；不因无法决定COLREG side而删除。Rule13 doubt另按DP-05保守duty。[R14]
- 备选 A: 无track/无效track等同“没有目标”，返回HOLD/SUCCESS。弃用草案理由: sensor failure与真实clear同形，产生危险假安全。
- 备选 B: UNUSABLE时继续执行cached old plan。弃用草案理由: 属未声明fallback，计划随时间失效，违反strict-no-fallback evidence。
- 备选 C: 忽略covariance/degraded，只使用固定CPA margin；或UNKNOWN_ROLE不占capacity。弃用草案理由: 不确定性和未分类威胁被系统性隐藏。
- 实现风险: 高。风险来自age主链当前缺失、covariance语义/相关性不完整、fail-stop对外部runtime控制权未定义。必须先补contract与status，不能只加布尔`degraded`。
- 失效边界: fail-stop不是实际避碰动作；Gaussian margin也不覆盖模型偏差/错误association。超出证据能力时必须UNKNOWN/UNUSABLE，不声称安全。
- 验证需求: missing-scan与true-no-target区分；NaN/PSD/age/covariance budget；degraded不release；coast不丢commit且最终UNUSABLE；strict solver-not-called/fail-stop；cached-plan禁止；UNKNOWN_ROLE active capacity；Gaussian/non-Gaussian provenance；session/web error evidence。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-12 多目标 aggregation（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-11 generation/episode、COASTING、rearm与三个弃用方向；写入 VR-11、ALT-31..33。
- 初步推荐: 顺序固定为`all observations -> all per-target lifecycle decisions -> rule/constraint aggregation -> immutable AggregateDirective -> L1最多16个NLP targets`。16-target限制不得反向删除Lifecycle state。[R5][R31][R32]
- pairwise output: 每目标保留phase、role、locked action/side、mandatory/conditional constraints、risk/clearance、health与priority evidence。Aggregate不是一个side sign，而是course corridor constraints、passing constraints、speed action bounds、conflict/capacity status及ranked target identities。
- priority: `MUST_ACT > committed GIVE_WAY > ACTION_CANDIDATE > MAY_ACT > STAND_ON WATCH > MONITOR`；同层按time-to-violation、positive TCPA、predicted/current hull clearance、stable identity排序。该矩阵是Planner ODD工程策略，不冒充COLREG总优先级。[R5][R33]
- constraint semantics: HO STARBOARD为mandatory；适用Rule17(c)为conditional port restriction；CS give-way保留avoid-ahead passing constraint；OT side commit前是preference、commit后是locked constraint。所有course candidate必须对全部active targets复核，不能只满足primary。[R14][R30][R31]
- conflict: mandatory/locked course constraints无共同可行corridor时输出`MANEUVER_CONFLICT`；允许形成substantial speed reduction/STOP directive，并保留全部冲突pairwise evidence。禁止静默用“最早TCPA”或“any starboard wins”覆盖冲突。[R14][R31]
- NLP capacity: 所有MUST/COMMITTED/ACTION_CANDIDATE/active safety threats必须入NLP；剩余slot按risk放WATCH/MONITOR。若active required targets>16，输出`CAPACITY_EXCEEDED`，L1不得截断第17个并假装SUCCESS；strict no-fallback runtime需显式failure/control-authority evidence。[R1][R40]
- primary target: 仅用于GUI/trace、风险解释与revision anchor；采用risk rank hysteresis，切换不重置任何其他target lifecycle。Primary不等于“只保证该船安全”。[R33]
- scope: aggregation证明Ship0候选动作同时考虑全部观测目标；不负责控制target vessels，也不把目标船之间固有collision计为Ship0 Mid-MPC planning failure。
- 备选 A: 最早TCPA target决定side，或`any mandatory starboard wins`。弃用草案理由: 可把Ship0转入第三目标，隐藏constraint conflict。
- 备选 B: facade先排序`[:16]`再做lifecycle/aggregation。弃用草案理由: 第17个active threat静默消失，core overflow永远不可见。
- 备选 C: 每个pairwise plan分别合规即可推出aggregate安全。弃用草案理由: Rule2/8与多船研究均要求动作不得形成另一close quarters，pairwise可行不保证共同可行。[R14][R31]
- 实现风险: 高。风险来自constraint-set表达、course/speed联合可行性、无统一法律priority matrix、>16 runtime contract。必须把工程priority/profile identity与conflict details暴露，不写场景特判。
- 失效边界: 所有course/speed action均不可行、active>16或observation unknown过多时，Aggregator只能输出显式conflict/capacity/uncertainty；不能创造安全解或fallback。
- 验证需求: HO+OT相反side；CS+Rule17 restriction；双侧course blocked→speed/stop；OT port/starboard mirrors；primary切换不重置；17th active target capacity failure；monitor填slot；每个active target出现在snapshot/trace；Ship0安全与target-target collision分开记账。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-11 Rearm、track loss 与 ID reuse（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-10 联合release、dynamic margin、恢复期监视与三个弃用方向；写入 VR-10、ALT-28..30。
- 初步推荐: lifecycle state key为`(target_id,generation)`，episode identity另行单调生成；release结束一次episode，不永久豁免同一track。`released_target_ids`删除。[R14][R34][R35]
- observation health path: `OBSERVED -> COASTING -> LOST`与lifecycle phase正交。短期COASTING保留locked encounter/role/side/commitment，不推进entry/release/achievement/reclassification等需要新观测的正向证据。[R35][R36]
- coasting model: 使用tracker提供的predicted state/covariance/age；compatibility path可用CV propagation，但必须随age增长covariance/margin并标source。禁止adapter默认age=0或Lifecycle无限CV coasting。[R36][R39]
- reacquisition: 同generation在`reacquisition_window_s`内恢复OBSERVED并继续原episode；identity facts须通过continuity validation。超出window或generation改变，不继承旧commitment；新identity立即重新评估risk，不等待旧tombstone过期。
- identity discontinuity: 位置/速度/时间跃变不可能由maneuverability envelope解释时输出`IDENTITY_DISCONTINUITY`。真实generation权威仍归tracker；legacy generation=0时终止旧episode、建立新episode且标`identity_quality=DISCONTINUOUS/LEGACY_UNKNOWN`，不得无声继承。[R34][R38]
- rearm sequence: PAST_CLEAR/RELEASED后先满足安全分离确认；随后同generation重新approaching并重新满足DP-06 entry与DP-07 confirmation，创建new episode/commitment。PAST_CLEAR前风险恶化属于原episode escalation，不叫rearm。
- tombstone: RELEASED/LOST episode保留有限`tombstone_ttl_s`，只用于审计、late duplicate与generation continuity；不阻止新generation/新risk进入。reset清空active states与tombstones。
- parameters: `coast_timeout_s/reacquisition_window_s/tombstone_ttl_s/discontinuity gates`均为physical-time Planner ODD参数。IMO/论文无通用数值；不得直接把adapter 1s/5s或VIMMJIPDA 5 missed steps提升为标准。[R35][R36][R38]
- 备选 A: 永久`released_target_ids`。弃用草案理由: 同目标真实二次风险被屏蔽。
- 备选 B: 目标缺失一周期立即删除全部state。弃用草案理由: 瞬时漏检消除Rule13/commitment duty，恢复后重新抖动。
- 备选 C: 仅裸target_id，无generation/discontinuity/tombstone。弃用草案理由: ID reuse继承旧动作，tracker语义差异不可审计。
- 实现风险: 高。风险来自当前tracker不交generation/age/status、legacy continuity只能保守推断、coasting covariance calibration。迁移需先扩tracker contract或显式legacy adapter，不能让Lifecycle私自假装association权威。
- 失效边界: 长时间观测丢失、错误tracker association或未知maneuverability下identity continuity不可证明；应进入DEGRADED/LOST policy，不能自动release或安全rearm。
- 验证需求: one-frame loss不丢commit；coast age/covariance增长；same-generation reacquire；new-generation不继承；legacy impossible jump；PAST_CLEAR前风险恶化；release后同目标rearm新episode；tombstone不阻塞新risk；reset清空；不同solve period时间语义一致。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-10 Release 与 past-and-clear（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-09 Rule17三阶段、target-action evidence、target-alone proxy与三个弃用方向；写入 VR-09、ALT-25..27。
- 初步推荐: `COMMITTED -> PAST_CLEAR -> RELEASED`。CPA passed只是必要事实之一；release联合有效观测、footprint-aware current clearance、持续分离、future clearance与physical confirmation time。[R14][R25][R26]
- common PAST_CLEAR gate: valid/non-UNUSABLE observation；CPA已通过；真实hull clearance达到dynamic release margin；closing rate转为持续separating；guard horizon内预测clearance不再次跌破；条件连续满足`release_confirm_s`。单帧distance rising或`signed_tcpa<=0`不足。[R14][R25]
- dynamic margin: 先从center geometry扣除双方沿相关轴的hull projection，再要求 `margin=max(minimum_margin_m, size_factor*reference_length, relative_speed*response_guard_time)`。`reference_length`至少含双方尺度；response guard使用`T_chi/T_U/r_max`及所需course/speed response。[R12][R13][R16][R25]
- OT additional gate: target-frame longitudinal hull clearance证明ownship整体已超前；lateral hull clearance满足locked passing side；relative motion持续离开且不再向target track收敛。禁止仅用center projection或固定190m。[R14][R30]
- recovery cut: 进入PAST_CLEAR输出`route_recovery_allowed=true`；LOS/L1决定恢复轨迹，L4复核。Lifecycle在恢复期间继续监视future clearance；风险重现时保持/升级原episode或按DP-11 rearm，不把route recovered作为Rule13 duty结束前置。[R26]
- RELEASED: PAST_CLEAR及恢复guard持续满足后结束episode并保留有限tombstone/evidence；不进入永久released set。Evaluator独立50m hard gate继续作为项目验收，不替代dynamic planner release，也不由release阈值反控。[R1][R42]
- prediction boundary: 首版future-clearance guard沿用带uncertainty的CV target prediction；目标突发机动是显式UNKNOWN/失效边界，guard horizon属于Planner ODD，不把IMO 3min或MPC 1200s当标准值。[R15][R20][R26]
- 备选 A: `signed_tcpa<=0`或CPA node通过即release。弃用草案理由: 不证明船体让清、持续分离或恢复轨迹安全。
- 备选 B: 固定190m或`k*own_length`。弃用草案理由: 无规则来源，忽略target尺度、相对速度、机动能力与passing axis。
- 备选 C: 一进入PAST_CLEAR立即删除state并恢复LOS，或等完全回到route才release。弃用草案理由: 前者失去恢复期re-risk，后者把下游route tracking错误变成COLREG duty条件。
- 实现风险: 高。风险源为dynamic margin标定、hull projection、future horizon、target sudden maneuver与恢复时序。需分别记录current/future/longitudinal/lateral evidence，不压成单一布尔值。
- 失效边界: 无效/丢失观测、未知target maneuverability或future prediction不可信时不得证明PAST_CLEAR；维持commitment或进入degraded policy，不能乐观release。
- 验证需求: CPA passed但hull未clear；单帧separation抖动；双方长度/relative speed/r_max scale；OT longitudinal/lateral mirror；固定190m删除；PAST_CLEAR允许恢复但state仍在；恢复中re-risk；target sudden turn；evaluator 50m独立gate。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-09 Rule17 stand-on escalation（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-08 absolute substantial commitment、动态幅度、OT双侧选择与三个弃用方向；写入 VR-08、ALT-22..24。
- 初步推荐: 对STAND_ON role使用显式 `STAND_ON -> MAY_ACT -> MUST_ACT`，三者分别表达 Rule17(a)(i)、17(a)(ii)、17(b) 的不同法律强度；禁止把进入NLP或TCPA≤90s解释为已升级。[R14][R27]
- STAND_ON: 默认 HOLD course/speed，同时持续观察target action与risk；HOLD不等于忽略target，也不阻止安全约束进入L1审计。
- appropriate-action evidence: 联合target course/speed trend、turning-point、predicted clearance improvement、remaining conflict、动作持续时间和target maneuverability reachability。单次heading变化或DCPA瞬时改善不足以判定appropriate。[R14][R28][R29]
- MAY_ACT: 当give-way target未在independent `latest_expected_action_s`/clearance boundary前形成持续、有效、可达的appropriate action时进入；其性质是“可以行动”，不强制立即复制give-way规则。阈值来自Planner ODD并记录trigger values。[R14][R27]
- MUST_ACT: 当接近critical clearance/time且工程近似判定give-way target单独行动已不能解除冲突时进入。推荐proxy为maneuverability-bounded target reachable velocity/trajectory set与conflict set相交性；若所需target facts不足，输出`TARGET_ALONE_FEASIBILITY_UNKNOWN`并由critical conservative guard触发，不伪造可行。[R14][R29]
- Rule17(c): 仅对power-driven crossing、依据17(a)(ii)的MAY_ACT，在circumstances admit时限制向port转向位于本船port侧的目标；不泛化到OT/HO，也不自动扩展为17(b) MUST_ACT绝对禁令。[R14]
- action mapping: MAY/MUST可形成DP-08的course、speed reduction或stop commitment；crossing MAY优先starboard/speed action以满足17(c)，MUST与多目标冲突交DP-12综合，所有departure/restriction必须evidence。
- 备选 A: crossing-stand-on/overtaken永久HOLD。弃用草案理由: 无17(a)(ii)/(b)升级，非合作目标场景只会被动进入危险。
- 备选 B: 仅以固定TCPA阈值切MAY/MUST。弃用草案理由: 规则触发依target action adequacy和target-alone capability；同TCPA不同净空/机动能力含义不同。
- 备选 C: 把Rule17(c)解释成所有stand-on/所有阶段永久禁止port或统一强制starboard。弃用草案理由: 扩大条文适用范围，且可能与17(b)/多目标即时危险冲突。
- 实现风险: 高。风险来自appropriate-action观测噪声、target maneuverability未知、reachable-set计算复杂度、MAY/MUST ODD标定。首版必须保守标UNKNOWN，不能用单一heading trend伪装充分判断。
- 失效边界: 未知target能力、非合作突发动作、多目标冲突可能使target-alone proxy不确定；Lifecycle只能输出明确phase/constraint/uncertainty，不能宣称法律等价证明。
- 验证需求: cooperative target保持STAND_ON；non-cooperative fixture产生MAY→MUST及reason；late/inadequate small action；target action改善后不升级；target-alone feasible/infeasible/unknown；17(c) port-side crossing；MUST多目标冲突；实际stand-on action与clearance closed-loop evidence。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-08 行为意图与 substantial commitment（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-07 physical-time confirmation、constraint-semantic lock 与三个弃用方向；写入 VR-07、ALT-19..21。
- 初步推荐: COMMITTED 生成 immutable `ManeuverCommitment`，至少含 baseline course/speed、action directive、passing side/constraint、absolute target alteration、achievement/revision/release evidence。每次 solve 使用同一 baseline，不做 `current_course + delta` 累加。[R14][R28][R30]
- action types: `HOLD/COURSE_ALTERATION/SPEED_REDUCTION/STOP`。Rule8允许course或speed action并要求明显、有效；Rule16要求early/substantial。优先course不表示任何情况下禁止速度动作。[R14]
- minimum action: 禁止固定 `+5°`，也不把用户举例的 `30°` 冒充COLREG常数。`substantial_course_delta_rad` 是 Planner ODD参数，须同时满足可观察最小动作、所需passing geometry、available action time与本船 `r_max/T_chi` 可达性；不可达则输出speed/stop candidate或MANEUVER_CONFLICT，不拆成连续小角增量。[R13][R16][R17][R28]
- persistence: minimum-alteration constraint 从commit开始持续激活，直到实际course/speed evidence达到commitment；不能只在`newly_committed`首轮启用。达到后继续维持locked passing corridor/clearance duty至DP-10 release，MPC可滚动更新轨迹但不重复叠加角度。
- role policy: HO course action锁定STARBOARD；CS give-way约束是avoid-ahead并在可行时采用明显starboard action；Rule17限制由DP-09；多目标冲突由DP-12。Side表示计划/实际passing geometry，不只看首个control sign。[R14][R30]
- OT policy: Rule13不规定固定passing side。commit前分别评估port/starboard corridor的predicted hull clearance、time-to-clear、route deviation、maneuverability与其他目标冲突；选择可行/代价较优侧，stable tie-break，commit后锁定。不得机械式固定右侧。[R14][R17][R24][R30]
- achievement: 由实际ownship trajectory相对commit baseline验证course alteration、speed reduction、passing-side geometry与clearance improvement；不能以command/constraint activation代替实际动作。[R30][R42][R45]
- controlled revision: 在`action_achievement_deadline_s`前未达到明显动作、风险不改善或原corridor变不可行时，产生离散revision candidate，可增加幅度或转speed/stop。Side switch仅在原侧不可行且不违反mandatory restriction时允许；必须before/after evidence，禁止左右振荡。[R14][R26]
- 备选 A: 当前固定5°且只首轮激活minimum row。弃用草案理由: 动作不明显、后续constraint消失、真实轨迹可近似直线。
- 备选 B: 所有HO/CS/OT统一固定30°。弃用草案理由: 30°不是规则常数，忽略船型、时间、净空、route与多目标可行性。
- 备选 C: OT固定STARBOARD passing。弃用草案理由: Rule13只规定keep out of way，不规定passing side；会拒绝更安全可行的port corridor。
- 实现风险: 高。风险源为action幅度ODD标定、OT双侧可行性、persistent hard direction对NLP可行性、实际achievement与L1 command延迟。需保留speed/stop与conflict显式路径，禁止fallback。
- 失效边界: 双侧course corridor均不可行、操纵剩余时间不足或solver无法满足commitment时，Lifecycle不能虚构合规course；必须输出MANEUVER_CONFLICT/CAPABILITY_LIMIT并由L1尝试speed/stop或fail-stop。
- 验证需求: baseline-relative non-accumulation；minimum row持续至actual achievement；固定5°完全消失；HO/CS实际明显动作；OT port/starboard mirror按态势选择；passing geometry而非首控符号；未达标revision；side-switch guard；course conflict→speed/stop；closed-loop actual trajectory evidence。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-07 Lock-on 与 hysteresis（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-06 联合 risk entry、CV baseline 边界与三个弃用方向；写入 VR-06、ALT-16..18。
- 初步推荐: candidate→COMMITTED 使用连续有效观测的 physical-time confirmation；`entry_confirm_s` 来自 Planner ODD。URGENT_CANDIDATE 可绕过普通确认，但必须产生 `urgent_bypass` evidence。[R5][R11]
- timer semantics: 只在 observation health 可用于 transition、candidate obligation 持续满足时推进；DEGRADED/COASTING 不增加确认时间，短暂 gap 可保留 candidate age但标 paused；LOST/identity generation change 按 DP-11 处理。禁止按 solve count 计时。
- candidate identity: confirmation key 不使用脆弱的组合 label，而使用 `(target generation, ownship role, required constraint semantics)`。HO↔CS 等变化只有在所需 obligation/constraint 语义等价时才续计；否则重置并记录 reason，不能简单“同 role 全合并”。
- commit lock: 进入 COMMITTED 时冻结 episode generation、locked encounter/role、preferred side、baseline course/speed、commit time 与 obligation semantics。instantaneous classification/risk 继续计算和记录，但不得因 ownship 已执行改向而覆写 locked facts。[R9][R10][R22]
- controlled revision: 目标真实、持续、可观测的大幅机动导致 obligation semantics 改变时，可经过独立 `reclassification_confirm_s` 形成 revision candidate；revision 必须离散、带 before/after evidence，不得自动左右翻转。动作是否不足及side revision归 DP-08。
- release boundary: lock 不能被单帧 `signed_tcpa<=0`、classification=CLEAR、primary target切换或目标未入前16解除；只由 DP-10 past-clear/release 或 DP-11 identity/loss/reset transition 结束。
- 备选 A: candidate 一出现立即 commit。弃用草案理由: measurement noise/boundary jitter 会制造 flicker，urgent 已有独立 bypass。
- 备选 B: 按固定 solve cycles 确认。弃用草案理由: 5s/其他调度频率改变业务时间，retry/hold 会扭曲计数。
- 备选 C: exact label 一变就重置，或所有 same-role label 无条件合并。弃用草案理由: 前者过度敏感，后者掩盖 HO starboard、CS avoid-ahead 等 constraint 语义差异。
- 实现风险: 中。主要风险为 constraint-equivalence key 设计、degraded timer 语义、真实 target maneuver 与噪声难分。所有时间参数必须 profile provenance，不能用 fixture 调参隐藏。
- 失效边界: hysteresis 只能抑制短期不稳定；错误 identity、持续错误 geometry 或不合理 ODD threshold 仍会稳定地锁错，必须靠 health/revision/L4 evidence 暴露。
- 验证需求: boundary jitter sequence；solve-period invariance；urgent bypass；degraded pause；HO/CS obligation-equivalence；ownship turn 后 instantaneous label变化但lock不变；target sustained maneuver controlled revision；primary切换不重置；retry不重复transition。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-06 风险阶段与进入条件（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-05 正交 classification/role、Rule13 doubt 与三个弃用方向；写入 VR-05、ALT-13..15。
- 初步推荐: L0 使用 role + approaching + physical TCPA + footprint/uncertainty-aware predicted hull clearance 联合形成 candidate facts；不直接从 classification 跳 COMMITTED，persistence 归 DP-07。[R5][R15][R19]
- baseline facts: `approaching=(signed_tcpa_s>0)`；`predicted_hull_clearance_m=center_dcpa - own_projected_extent - target_projected_extent - uncertainty_margin`；保留 current clearance、closing rate、TCPA、validity 与 threshold provenance。
- phase candidates: 有效几何但无预测风险→MONITOR；GIVE_WAY/MUTUAL_GIVE_WAY 且进入 action window→ACTION_CANDIDATE；STAND_ON 且进入 watch window→WATCH_REQUIRED；current/dynamic clearance 或 time-to-critical 进入紧急域→URGENT_CANDIDATE。UNDETERMINED/Rule13 doubt 且风险存在不得变 CLEAR，至少 WATCH_REQUIRED。[R14]
- nominal entry: valid observation；approaching；role applicable；`0<tcpa_s<=action_lead_time_s`；`predicted_hull_clearance_m<=entry_clearance_m`。`action_lead_time_s` 和 `entry_clearance_m` 来自独立 `PlannerOddProfile`，并须与 ownship response time、双方尺度/速度相容。[R13][R16][R18][R19]
- maneuverability guard: profile validation 至少检查 action lead time 不短于 course/speed response need，例如 `min_alteration/r_max + response_guard` 与 speed-change response；不是把 MPC `80×15s` 当业务窗口。
- urgent: current clearance/closing 或 time-to-critical 达独立 urgent boundary 时可绕过普通 entry confirmation，但仍必须输出触发 facts；数值留 Planner ODD calibration，不从 COLREG/evaluator 伪造。[R14][R17]
- prediction boundary: 第一实现以 deterministic CV-CPA 作为 L0 baseline；不在 Lifecycle 内引入 LOS/route/target motion predictor。CV 假设失效必须显式 evidence，L1 horizon/L4 swept-CPA 继续承担轨迹安全验证。[R20]
- 备选 A: `action_lead_time = horizon_steps × horizon_dt`。弃用草案理由: 业务行为绑定 optimizer discretization；1200s horizon 会导致极早 commitment。
- 备选 B: 复用 evaluator stage/risk thresholds。弃用草案理由: acceptance profile 反向控制 planner，50m evaluator gate 也不是通用 action-entry 值。
- 备选 C: 只用 DCPA、只用 TCPA 或只用 range。弃用草案理由: 分别产生远期误触发、安全通过误触发或无法表达 closing future risk。
- 实现风险: 高。风险来自 ODD 数值标定、CV target assumption、uncertainty margin 与 maneuverability facts 尚未校准。必须将参数 provenance 与触发值写入 evidence，禁止为单场景特判。
- 失效边界: target 突发机动、错误 covariance/identity、OOD vessel status、CV-CPA 无效时，L0 candidate 可能滞后或保守；不得声称 entry contract 独立保证 collision avoidance。
- 验证需求: risk truth table；DCPA/TCPA/range 单变量反例；horizon steps/dt 改变但 physical entry time 不变；船长/速度/r_max scale tests；urgent bypass；UNKNOWN/doubt 不 clear；HO/CS/OT onset timing closed-loop trace；与 evaluator profile 改动解耦。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-05 几何分类与角色映射（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-04 observation contract、legacy UNKNOWN 语义与三个弃用方向；写入 VR-04、ALT-10..12。
- 初步推荐: planner classifier 只产生正交 `EncounterKind`、`OwnshipRole` 与 classification evidence；不决定 risk、commit、action、side 或改向角。[R9][R14][R23]
- kinds: `HEAD_ON/CROSSING/OVERTAKING/CLEAR/UNDETERMINED`。Roles: `MUTUAL_GIVE_WAY/GIVE_WAY/STAND_ON/NONE/UNKNOWN`。
- mapping: HO→MUTUAL_GIVE_WAY；crossing target 在 ownship starboard→GIVE_WAY，port→STAND_ON；ownship overtaking→GIVE_WAY；ownship overtaken→STAND_ON；CLEAR→NONE；UNDETERMINED→UNKNOWN。[R14]
- threshold provenance: Rule13 的 more-than-22.5° abaft beam / 112.5° relative-bearing boundary 来自规则；HO reciprocal tolerance、crossing sector、minimum reliable SOG、relative-speed tolerance 是 `PlannerOddProfile` 工程参数，不能冒充规则常数。[R14][R17][R23]
- doubt semantics: 低速、无效 course、边界带或不支持的 vessel/navigation status 输出 UNDETERMINED/UNKNOWN，禁止吞成 CLEAR。若几何存在 Rule13 overtaking doubt，额外输出 `overtaking_doubt=true`，供后续 duty/risk 层落实“有疑问按追越处理”，而不伪造确定 label。[R14][R35][R37]
- risk separation: classification 不以 DCPA/TCPA/range 是否安全为前置；远距离或当前 predicted clearance safe 的船仍可有 HO/CS/OT geometry，只处于 CLEAR/MONITOR risk phase。signed TCPA/DCPA 仅作为 geometry evidence 交 DP-06。
- 备选 A: 保留 `crossing_give_way/overtaking/...` 组合字符串。弃用草案理由: encounter、role、risk、action 焊死，阻碍 Rule17、lock 与双船镜像审计。
- 备选 B: 只有 DCPA/TCPA 达风险阈值才分类。弃用草案理由: 无法提前 monitor/lock，risk profile 改动会重写规则事实。
- 备选 C: 边界/低速/缺失值 fallback 为 CLEAR 或最近 label。弃用草案理由: CLEAR 假阴性或无 evidence 的静默确定性；历史保持应由 DP-07 lock 处理。
- 实现风险: 中。风险源为当前 classifier 行为差异、角度 convention、overtaking/overtaken 对称性、项目 ODD 未携 vessel type/status。必须先锁 ENU/heading/bearing convention 与 ODD applicability。
- 失效边界: 对非 power-driven、狭水道/分道通航、锚泊/失控等当前 contract 未覆盖情形输出 UNDETERMINED/ODD_UNSUPPORTED；不能用 Rule13-17 power-driven mapping 硬套。
- 验证需求: HO/CS port-starboard/OT-overtaken 镜像 table tests；112.5°及 profile boundary epsilon；远距离分类不变；低速/共速/无效 course；Rule13 doubt；classification 与 risk threshold 独立性；与 evaluator verdict 不共享 expected label。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。
- 用户确认: 2026-08-11，采纳初步推荐与三个弃用方向；写入 VR-01、ALT-01..03。该确认是 Step4 推荐裁决，不替代 Step5 DESIGN-IT-TWICE。

### Step4 · DP-03 Lifecycle 技术与状态表达（推荐草案） [2026-08-11]

- 初步推荐: 采用逐目标、确定性、有记忆的 pure FSM，但不用单一巨型 enum；状态由少量正交 typed facts 组合，并由一个 transition function 原子更新。[R5][R9][R10][R22]
- lifecycle phase: `CLEAR -> MONITOR -> CANDIDATE -> COMMITTED -> PAST_CLEAR -> RELEASED`。它只表达 encounter episode 的时间进程；rearm 可从 RELEASED 经新 candidate 创建新 episode。[R14][R26]
- 正交 axes: `instantaneous_encounter`、`locked_encounter`、`ownship_role`、`rule17_phase(STAND_ON/MAY_ACT/MUST_ACT)`、`action_directive(HOLD/COURSE/SPEED_REDUCTION/STOP)`、`preferred_side`、`observation_health(OBSERVED/DEGRADED/COASTING/LOST/UNUSABLE)`、commitment/release/identity/evidence facts。具体成员由 DP-05/08/09/11/13 继续裁决。
- invariant: COMMITTED 必须有 episode identity、locked role/encounter、baseline/commitment facts；PAST_CLEAR 必须有 release evidence；RELEASED 不永久豁免；health 不覆盖 duty/action，LOST 不自动等于 CLEAR。
- 证据链: Rule13 duty 不因瞬时 bearing 改变；peer-reviewed/MASS state machines 支持 per-target onset lock 与离散状态在连续优化周期内冻结。没有来源支持唯一 monolithic minimal enum，因此以正交 facts 控制状态爆炸。[R9][R10][R14][R22]
- 备选 A: 每周期 stateless classify→intent。弃用草案理由: ownship 改向后 label flicker，commitment、Rule17、release/rearm duty 丢失。
- 备选 B: 单一 enum 编码 encounter×role×phase×side×health×emergency。弃用草案理由: 组合爆炸、非法状态难审计，后续扩展必然破坏兼容。
- 备选 C: 复用 evaluator `PairwiseColregFSM`。弃用草案理由: 状态集合围绕评分 stage，不覆盖 planner commitment、generation、coasting、aggregate conflict 与 atomic handoff。
- 实现风险: 中。最大风险是正交 facts 产生互相矛盾组合。约束为 transition function 私有构造 next state，public DTO immutable，集中 invariant validation；禁止调用者逐字段 mutation。
- 失效边界: FSM 不创造缺失 observation/identity，不替代 target prediction，不决定 numerical ODD threshold，也不保证 L1问题可解；对应输出 UNKNOWN/health/conflict/status。
- 验证需求: transition table tests；所有 public state 通过 invariant validator；非法组合 construction tests；same input/cycle deterministic；one solve cycle locked facts immutable；序列测试覆盖 flicker、Rule17、past-clear、rearm、coasting、reset。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step4 · DP-02 态势分类权威来源（推荐草案） [2026-08-11]

- 初步推荐: 把纯物理计算提升为 planner-neutral `PairwiseGeometry` seam；它只从双方 kinematics/hull/time 计算 range、relative bearing、relative velocity、DCPA、signed TCPA 与 validity，不输出最终 COLREG role/action。[R1][R20][R21]
- planner 权威: Encounter Lifecycle 内的 planner classifier 消费 `PairwiseGeometryFacts + PlannerOddProfile`，产生 instantaneous encounter candidate/role。112.5° OT 等规则边界进入 Planner ODD/profile；HO/CS tolerance、低速/边界 unknown 语义由后续 DP-05 裁决。[R14][R17][R23]
- evaluator 边界: evaluator 可复用坐标/CPA 等无政策数学 primitive，但必须使用 evaluator 自己的 profile、FSM、stage 与 acceptance semantics；不得把 planner locked label/role 当作评分真值。[R21]
- 证据链: 当前 Mid 从 evaluator package import `classify_geometry`，且该函数包含 label/fallback；evaluation/protocol certification 与 planner decision 是不同责任。CVM CPA 是有效 baseline，但 target maneuver/低速/边界均有已知限制。[R1][R20][R21][R23][R35][R37]
- 备选 A: 保持 `integrations.mid_mpc_ipopt -> evaluation.encounter.classify_geometry`。弃用草案理由: 包依赖方向错误，分类阈值/hidden fallback 与 evaluator 演进直接改变 planner。
- 备选 B: 在 lifecycle 复制整套 geometry/classifier。弃用草案理由: 物理公式漂移、坐标/符号重复 bug，难以证明 planner/evaluator 差异来自 policy 而非数学实现。
- 备选 C: evaluator FSM 输出直接作为 PlannerInput。弃用草案理由: 评分器成为控制 authority，闭环测试可能自证。
- 实现风险: 中。风险源为 current classifier 的行为兼容、GUI instantaneous badge 消费、角度边界差异。迁移应先建立 geometry golden tests，再切 planner import；不同时改 evaluator policy。
- 失效边界: pure geometry 不解决 target prediction、track identity、低速 COG 无效或 classification ambiguity；这些必须以 validity/UNKNOWN facts 交给 lifecycle，不允许 hidden fallback 伪造确定标签。
- 验证需求: 当前普通 HO/CS/OT 数学 golden parity；signed TCPA/DCPA/relative-bearing 单位与符号 tests；低速/共速/边界/非有限输入；dependency test 禁止 planner import evaluator；现有 evaluator G3结果独立复跑。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。
- 用户确认: 2026-08-11，采纳 planner-neutral geometry 与 planner/evaluator policy 分离；写入 VR-02、ALT-04..06。该确认是 Step4 推荐裁决，不替代 Step5 DESIGN-IT-TWICE。

### Step3 · Batch-3 tracking、handoff、schema 与 observability 证据  [2026-08-11]

- 覆盖盲区: BL-05/08/09/14/15/34/35/36/37/38/43/44/45/46/47/48/49/50/51/52/53/54/56。
- track identity 事实: God/KF 使用 scenario ID；VIMMJIPDA 内部产生新 track index 与 existence/missed-step facts，但公共 contract 只输出裸 ID/state/cov/hull。当前 lifecycle 无 generation，连续 ID 可错误继承，单周期缺席又立即遗忘。[R34][R36]
- release/rearm 事实: 当前 released suppression 对持续可见 ID 近似永久；缺席一周期则清除。Rule5/7/8 要求持续 lookout/risk assessment，但不定义软件 rearm、tombstone 或 reacquisition seconds。[R14][R34][R35]
- degraded/coasting 事实: Ship 主链未传 track age；默认所有 track fresh。Covariance 只做 finite/symmetric/PSD 校验，Mid 不将 degraded/covariance 纳入 classification、margin 或 policy。KF 内部可无限 CV predict，Planner 看不到 coast age。[R34][R36]
- uncertainty 证据: χ² confidence ellipse 可把 Gaussian covariance 转成 probability-scaled margin，但 confidence level、covariance composition、non-Gaussian/risk budget 均无通用答案。[R38][R39]
- maneuverability contract 事实: Ship 传入 `T_chi/T_U/r_max`，PlannerInput 静默丢失；Mid 使用独立 `3 deg/s`、`0.3 m/s²` 配置。IMO 支持 turning/course-change/stopping facts 重要，不规定 Playground DTO 或两条约束链必须数值相同。[R13][R16][R40]
- runtime 事实: 观测不可用与“无目标”当前同形；显式超龄会 INVALID_INPUT 并使 Session fail-stop，无旧 plan fallback，但无 observation-specific status/control-authority contract。[R40]
- atomic/idempotency 事实: 当前只有 run UUID、成功 solve_id；无 session epoch/cycle identity/input hash。Facade 在 solver 前 mutation，失败 retry 无 rollback；reset 无 reason/epoch，正向大 gap 不拒绝。ROS 2 只提供 jump mechanism，不给阈值。[R40][R41]
- schema/retention 事实: PlannerTrace 顶层 1.0，但 algorithm_details 无 lifecycle sub-schema；session events 无界积累，结束时 batch 写 JSONL；GUI 的 500/60 仅展示裁剪。CloudEvents/OTel 提供 envelope、schema 与 exporter 先例，不给本项目容量。[R42][R43][R46]
- provenance 事实: registry 已 hash profile mapping，但 absolute dependency path 参与 hash；trace 只有聚合 build identity。RFC8785 可提供 canonical JSON，是否采用、排除哪些 deployment fields 仍 UNKNOWN。[R42][R44]
- GUI/acceptance 事实: 默认风险卡来自 evaluator-side instantaneous monitor；planner card 未展示 locked role/phase/reason/health/release/conflict/profile。单遭遇只证 command angle，未证 actual trajectory 在 commit→past-clear 窗口达到 substantial action。[R42][R45]
- BL-09 调研路径: NLM SOCKS 仍未修复；Step3 已由当前 CodeGraph project facts、IMO/USCG/ROS 2/IETF/CNCF 一手来源与同行评审论文覆盖。工具故障不再构成证据缺口；是否接受该替代路径仍待用户确认。
- 本批保留 UNKNOWN: generation/ID continuity owner；coast/reacquire/tombstone/discontinuity 数值；COG/covariance/age 阈值；confidence/risk budget；UNUSABLE control-authority contract；cycle key/reset/gap policy；schema兼容窗口；buffer容量/overflow；GUI层级；actual substantial angle/window。
- 状态: 证据已写入 EV；本批盲区保持“调研中”，等待用户确认。
- 用户确认: 2026-08-11，Batch-3 证据充分；接受所有剩余 UNKNOWN 进入 Step4 工程/Planner ODD 裁决。BL-09 以 CodeGraph、官方标准及一手论文替代 NLM 路径，证据阻塞解除。
- Step3 gate: BL-01..BL-58 全部已有证据或显式 UNKNOWN，三类置信度已分列；TD-01 全部子模块盲区覆盖完成。用户已授权进入 Step4。
- 日志顺序注: Step4 DP-01..03 草案在 Batch-3 确认落盘前后并发插入；权威状态以 0.1/0.6/0.7 注册表和各草案的用户确认行判断。

### Step4 · DP-04 Pairwise observation contract（推荐草案） [2026-08-11]

- 前项确认: 用户于 2026-08-11 采纳 DP-03 正交 typed-facts FSM 与三个弃用方向；写入 VR-03、ALT-07..09。该确认不替代 Step5 DESIGN-IT-TWICE。
- 初步推荐: `EncounterCycle` 保存一次 cycle header/ownship facts，包含 session epoch、cycle identity、sim time、dt、ENU ownship position/velocity/heading、hull 与 maneuverability envelope；`PairwiseEncounterObservation` 每目标保存 identity、target kinematics/hull、observation provenance/quality、planner-neutral geometry facts。[R13][R16][R34][R40]
- identity: typed `(target_id,generation)`；generation 应由 tracker association 提供。Legacy tracker 仅可显式 `generation=0 + identity_quality=LEGACY_UNKNOWN`，不得宣称跨周期身份稳定。[R34][R35][R36]
- kinematics: ENU/SI/rad；position/velocity 必填且 finite；true heading 可选并带 validity；velocity-derived COG/SOG 单独给出，低于 profile threshold 时 `cog_valid=false`，不把 `atan2(0,0)` 当真实航向。[R35][R37]
- geometry: 引用 DP-02 的 range、relative bearing/velocity、DCPA、signed TCPA 与 validity；它们是 snapshot facts，不含 encounter label、role、risk stage 或 action。
- observation provenance: `observed_at_s`、`age_s`、covariance、source/tracker identity、association/track status、quality/validity reason。未知 age/quality 必须显式 UNKNOWN；禁止默认 `age=0` 伪造 fresh。[R34][R35][R38][R40]
- hull/maneuverability: 双方 length/width 必须保留；ownship `T_chi/T_U/r_max` 与 course/speed/deceleration envelope 进入 cycle-level facts，不能只留 hull，也不能让 Mid 配置成为隐式 plant truth。[R13][R16][R40]
- 备选 A: Lifecycle 直接消费 `PlannerInput/TrackedObstacle`。弃用草案理由: 泄漏 route/tracker/MPC adapter，且现有 DTO 对 age/generation/maneuverability 表达不完整。
- 备选 B: 只传 ID、position、velocity。弃用草案理由: 无法判断 stale、low-speed、identity reuse、uncertainty 或 dynamic clearance。
- 备选 C: 缺失 generation/age/heading 时填 `0` 或当前时间。弃用草案理由: 把未知伪装成精确事实，导致错误 release/rearm/classification。
- 实现风险: 中高。风险源为 tracker contract 扩展、legacy trackers 缺字段、covariance layout 与 Ship kwargs 不一致。迁移必须经显式 compatibility adapter；不能在 Lifecycle 内猜值。
- 失效边界: observation DTO 不修复 tracker association、传感器误差或低速不可观测性；只保持 provenance/validity，使 DP-11/13 可确定处理。
- 验证需求: frozen DTO/finite/PSD/units tests；legacy identity/unknown-age tests；同 ID 新 generation；低速 COG invalid；maneuverability 不丢失；policy-field absence test；JSON round-trip；多目标同 cycle ownship/time 一致。
- 状态: 草案已展示前待确认；未写入 VR/ALT，不是 final。

### Step6 · 术语、技术规约与方案包草案 [2026-08-11]

- 用户授权: 2026-08-11，明确授权进入Step6。
- 方案包: `docs/superpowers/specs/2026-08-11-mid-mpc-l0-l1-encounter-lifecycle-solution-pack.md`。
- 组件1术语表: 28个术语，覆盖L0/L1、identity/episode、FSM/Rule17、passing side、aggregate、profile与actual evidence；每项定义本方案语义和非语义边界。
- 组件2技术规约: TS-01..TS-36，六类齐全；锁定ENU/N-E、starboard-positive、SI/rad、80 intervals×15s/81 states、epoch/cycle/hash、track health、dynamic clearance、Rule17/release、Tracker/Lifecycle/Assembler/Trace/GUI契约。
- 组件3决策卡: VR-01..VR-21全部收录；Step5五张card final方案与替代项明确。
- 组件4证据矩阵: R1..R46全部收录；完整书目/链接/置信度仍以本日志0.4和参考文献为权威。
- 组件5技术分解: TD-01所有子模块、owner、输入输出、状态及工程切片顺序齐全；无DECOMPOSITION_INCOMPLETE。
- 组件6弃用方案: ALT-01..ALT-58按主题完整覆盖。
- 组件7场景/验收: HO、OT双镜像、CS GW/SO cooperative/non-cooperative、overtaken、multi compatible/conflict、flicker、track loss/reuse、reset/capacity/core mismatch；A/B/C/D gate与8010门明确。
- 组件8冲突/UNKNOWN: K-01..K-12均有disposition和阻塞边界；COLREG无数值、frozen core global side、80/81 grid、CPA indexing、target dynamics、CV/Gaussian、target-target等未隐藏。
- 新发现并固化: raw solver有80个15s decisions，但当前public trajectory仅80 samples/t=0..1185；TS-14规定raw parity不变，public mapping必须81 states/t=0..1200。
- 验证: `git diff --check`通过；方案包八组件齐全；TS-01..36在方案包与日志各36项；R1..46证据46项；K-01..12已知边界12项。
- 用户接受: 2026-08-11，明确“接受方案包”；Step6 gate通过。
- 交付更新: 本机已移除superpowers技能；权威链改为`design-grounding → to-spec → implement+tdd → code-review`。本方案包交付to-spec，禁止重新比较已弃用架构或修改TS，除非新证据触发回炉。
- to-spec交付: 设计Spec与实施文档已生成；ready-for-agent issue [#24](https://github.com/marinehdk/colav-simulator/issues/24) 已发布。
- 状态: Step6完成，已交付to-spec；下一链路为implement+tdd，完成后code-review。
