# 设计日志: 动态 MPC 避碰 Playground

> **模式**: 重构        **创建**: 2026-07-27
> **关联方案包**: `docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md`
> **状态**: Step6 完成；方案包已交付 brainstorming；术语表+技术规约表（六类）+八组件方案包齐；等待用户接受后调用 brainstorming
> **工作分支**: `codex/colav-backend-algorithms`
> **设计对象**: 复用上游 COLAV-Simulator，建立用于 Custom MPC 正确性、有效性和公平对比的动态避碰 Playground
> **取代旧日志**: `2026-07-27-mpc-colav-simulation-validation-platform-design-log.md`

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|---|---|---|---|---|---|
| DP-01 | 平台核心范围：只建设动态 MPC 避碰 Playground，不复制生产级 TDL | 架构 | - | 已裁决 | VR-01 |
| DP-02 | 论文复现仅在对应算法达到 G3 后作为条件实验包启用 | 架构 | - | 已裁决 | VR-02 |
| DP-03 | RRT 静态规划和 VIM 跟踪仅按 Custom MPC 验证需要启用 | 架构 | - | 已裁决 | VR-03 |
| DP-04 | `Custom MPC` 指用户自研 MPC，通过统一 Adapter 接入 | 接口 | - | 已裁决 | VR-04 |
| DP-05 | 标准场景包来源、旧 schema 迁移、episode/map SHA 和重建置信度 | 架构 | - | 调研中 | Step2 DP-05 |
| DP-06 | Playground ODD 与最小覆盖矩阵：HO、crossing、overtaking、multi-ship、ENC | 约束 | - | 调研中 | Step2 DP-06 |
| DP-07 | Nominal、VO、SB-MPC、外部 MPC、Custom MPC 的资格顺序和进入条件 | 架构 | - | 调研中 | Step2 DP-07 |
| DP-08 | 统一 Custom MPC 插件契约 | 技术 | TD-01 | 调研中 | Step2 DP-08 |
| DP-09 | 本船、Track/协方差、ENC、参考航线、目标和扰动输入语义 | 接口 | TD-01 | 调研中 | Step2 DP-09 |
| DP-10 | 执行指令、当前计划和统一 `9xN` 预测轨迹输出语义 | 接口 | TD-01 | 调研中 | Step2 DP-10 |
| DP-11 | 算法声明元数据：状态、控制、预测模型、时域、目标函数和约束 | 接口 | TD-01 | 调研中 | Step2 DP-11 |
| DP-12 | `plan/reset` 生命周期、规划周期、deadline、seed 和状态保持 | 接口 | TD-01 | 调研中 | Step2 DP-12 |
| DP-13 | 成功、超时可行、不可行、数值失败、依赖缺失和 fallback 政策 | 约束 | TD-01 | 调研中 | Step2 DP-13 |
| DP-14 | PlannerTrace 必需诊断、算法专项字段及 solve/hold 语义 | 接口 | TD-01 | 调研中 | Step2 DP-14 |
| DP-15 | 最小闭环仿真验证夹具 | 技术 | TD-02 | 调研中 | Step2 DP-15 |
| DP-16 | truth→sensor/tracker→MPC→guidance/control→ship model→log 相位和多率关系 | 架构 | TD-02 | 调研中 | Step2 DP-16 |
| DP-17 | 被测 MPC 模型、执行控制器和仿真船模的模型失配边界 | 算法 | TD-02 | 调研中 | Step2 DP-17 |
| DP-18 | ENC、风流、船体尺度、碰撞/搁浅/目标到达的环境与终止语义 | 约束 | TD-02 | 调研中 | Step2 DP-18 |
| DP-19 | 场景、量测、Tracker、扰动和算法随机流的确定性重放 | 架构 | TD-02 | 调研中 | Step2 DP-19 |
| DP-20 | MPC 独立评价与资格认证体系 | 技术 | TD-03 | 调研中 | Step2 DP-20 |
| DP-21 | 碰撞、最小船距、CPA/TCPA、搁浅和 ENC clearance 安全 oracle | 约束 | TD-03 | 调研中 | Step2 DP-21 |
| DP-22 | Rules 8、13、14、15、16、17 的分类、角色和行为 oracle | 算法 | TD-03 | 调研中 | Step2 DP-22 |
| DP-23 | 任务完成、路径恢复、延误、控制跟踪和求解性能指标 | 约束 | TD-03 | 调研中 | Step2 DP-23 |
| DP-24 | G2/G3/G4 证据门、组合兼容性及自动晋级/降级政策 | 架构 | TD-03 | 调研中 | Step2 DP-24 |
| DP-25 | 公平 episode、seed 数、失败样本保留、统计量和置信区间 | 约束 | TD-03 | 调研中 | Step2 DP-25 |
| DP-26 | manifest、trajectory、events、PlannerTrace、evaluation 和 replay 证据包 | 接口 | TD-03 | 调研中 | Step2 DP-26 |
| DP-27 | 外部/原生算法隔离 Worker | 技术 | TD-04 | 调研中 | Step2 DP-27 |
| DP-28 | in-process/worker 边界、依赖 profile、代码及运行时身份 | 架构 | TD-04 | 调研中 | Step2 DP-28 |
| DP-29 | Worker 请求/响应、超时、退出码、stderr 和崩溃恢复语义 | 接口 | TD-04 | 调研中 | Step2 DP-29 |
| DP-30 | PSB-MPC/RLMPC 原生轨迹、状态和诊断到公共契约的归一化 | 接口 | TD-04 | 调研中 | Step2 DP-30 |
| DP-31 | 后端向 Web Viewer 输出实时状态、规划诊断、评价和证据的只读边界 | 接口 | - | 调研中 | Step2 DP-31 |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|---|---|---|---|
| TD-01 | Custom MPC 插件契约 | 输入(DP-09)、输出(DP-10)、算法声明(DP-11)、生命周期/时序(DP-12)、失败/fallback(DP-13)、诊断(DP-14) | Step1 |
| TD-02 | 最小闭环仿真夹具 | 相位/多率(DP-16)、模型失配(DP-17)、环境/终止(DP-18)、确定性重放(DP-19) | Step1 |
| TD-03 | 独立评价与资格认证 | 安全(DP-21)、COLREGS(DP-22)、任务/控制/求解(DP-23)、能力门(DP-24)、公平统计(DP-25)、证据包(DP-26) | Step1 |
| TD-04 | 外部算法 Worker | 隔离/运行时身份(DP-28)、通信/崩溃(DP-29)、公共契约归一化(DP-30) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|---|---|---|---|---|
| BL-01 | PSB corpus 旧 `model.telemetron` 字段应映射还是删除；需要历史 schema/船模证据 | DP-05 | 高 | 已闭环：用户确认映射为 `model.viknes`，不得删除 |
| BL-02 | 历史 ENC 与当前 ENC 的许可、版本、几何和安全水域等价性 | DP-05 | 高 | 边界已确认：easy 窗口几何等价；Agder 与历史许可保留 `EXTERNAL_CONFIRMATION_REQUIRED` |
| BL-03 | 每类 100 个 episode 中最小认证集的抽样/选取规则 | DP-05 | 中 | 已闭环：上游无缩减集；本项目 G3 数量转 BL-80 |
| BL-04 | Custom MPC 预期船型、速度、水深和可操纵范围 | DP-06 | 高 | 边界已闭环：V1 为 Viknes reference ODD；FCB45 target ODD 保留 `EXTERNAL_CONFIRMATION_REQUIRED` |
| BL-05 | 每条规则达到 G3 所需的最小几何变体数量 | DP-06 | 高 | 边界已闭环：采用 covering-array t=2 方法 + 声明为本项目新建 regression set；具体数量待 BL-80 |
| BL-06 | multi-ship 是否作为首个 Custom MPC 里程碑完成门 | DP-06 | 中 | 已闭环：用户确认后置 V3 |
| BL-07 | 风流扰动进入 V1，还是基础无扰动通过后启用 | DP-06 | 中 | 已闭环：用户确认后置 |
| BL-08 | VO/SB-MPC 是否必须各自覆盖全部四类双船规则 | DP-07 | 高 | 已闭环：每类至少一个 G3 对照即可 |
| BL-09 | 各场景“有效风险基线”和“对照算法通过”的定量阈值 | DP-07 | 高 | 已闭环：风险资格、物理硬门、Evaluator profile 三层分离；具体数值门归 DP-20..25 |
| BL-10 | Custom MPC 首次交付形式和运行环境 | DP-07 | 中 | 已闭环：`CustomMPCAdapter(ICOLAV)` 薄适配器；in-process 优先；Worker 后置 |
| BL-11 | 扩展现有 `ICOLAV.plan` 参数，还是在 Adapter 内引入 typed request DTO | DP-08 | 高 | 已闭环：Adapter 内 typed `PlannerInput` DTO；保持 `ICOLAV.plan()` 签名兼容 |
| BL-12 | 坐标、单位、时间有效性和 Track 数据质量的 Adapter/solver 验证边界 | DP-08 | 高 | 边界已闭环：Adapter 验证坐标/单位/时间/Track 质量；solver 判断优化可行性；技术规约 Step6 锁定 |
| BL-13 | Custom MPC 配置 schema、版本和参数身份记录方式 | DP-08 | 中 | 已闭环：`AlgorithmDescriptor` 版本化可哈希 config；manifest 冻结副本 |
| BL-14 | Track 最大允许 age；过期后拒绝还是标记降级 | DP-09 | 高 | 边界已闭环：Track age profile 化 + degraded 标志；具体秒数后置 |
| BL-15 | covariance 坐标系、状态顺序、PSD 容差及缺失政策 | DP-09 | 高 | 已闭环：covariance 坐标系/状态顺序与 ownship 一致；PSD 检查；缺失 → INVALID_INPUT |
| BL-16 | MPC 接收完整 ENC 对象，还是裁剪后的可序列化 hazard geometry | DP-09 | 高 | 已闭环：in-process 传完整 ENC；Worker 传裁剪 hazard geometry + SHA |
| BL-17 | 目标船 length/width 缺失或不可信时的处理政策 | DP-09 | 中 | 已闭环：缺失 → INVALID_INPUT；不可信 → degraded；fallback footprint 显式标记 |
| BL-18 | horizon 第 0 列表示当前状态还是下一控制时刻 | DP-10 | 高 | 已闭环：horizon 第 0 列 = solve-time 当前状态；selected_command 单独字段 |
| BL-19 | solver 状态维度不是 9 时，加速度/缺失状态的映射方式 | DP-10 | 高 | 已闭环：`StateMapping` 版本化映射；缺失维度填 0 标 `estimated=false` |
| BL-20 | 输出轨迹连续性、物理一致性和首点误差容差 | DP-10 | 高 | 边界已闭环：连续性检查（motion bound 上界）；首点误差 ≤ footprint tolerance；具体数值后置 |
| BL-21 | `selected_control` 表示参考指令还是原始 MPC 控制量 | DP-10 | 中 | 已闭环：selected_command = 控制器兼容参考；原始控制量进 algorithm_details；同 solve_id |
| BL-22 | `AlgorithmDescriptor` 强制字段与允许 `not_applicable` 字段 | DP-11 | 高 | 已闭环：强制 12 字段 + 允许 not_applicable 字段 |
| BL-23 | 外部二进制/服务的代码 SHA、build 和依赖身份获取方式 | DP-11 | 中 | 已闭环：build_identity 携带 SHA/binary/solver/build flags；缺失标 UNKNOWN |
| BL-24 | 自适应权重、动态 horizon 和在线模式切换的记录方式 | DP-11 | 高 | 已闭环：静态进 Descriptor，动态进 algorithm_details 绑 solve_id |
| BL-25 | 目标函数和约束名称是否需要公共分类词表 | DP-11 | 中 | 已闭环：公共 cost/constraint 分类词表；不横向比较 |
| BL-26 | 首次求解发生在 `t=0` 还是首个 `dt_sim` 后 | DP-12 | 高 | 已闭环：首次 solve 在 t=0；solve_id=1 首步 |
| BL-27 | solve period/deadline 由算法声明，还是允许 RunSpec 覆盖 | DP-12 | 高 | 边界已闭环：solve_period 算法声明 + RunSpec 可覆盖；deadline profile 后置 |
| BL-28 | 非求解步对上一 horizon 采用采样推进、插值还是固定第一指令 | DP-12 | 高 | 已闭环：hold 步保留 horizon 原点，按 t_now 采样；不重新 solve |
| BL-29 | warm start 与随机求解器的 reset/replay 保证范围 | DP-12 | 高 | 已闭环：reset 清 warm start；无 seed API 不获 exact |
| BL-30 | 离线快速仿真是否也强制实时 deadline | DP-12 | 中 | 已闭环：离线可关 deadline，标 diagnostic_only 不进 G3 |
| BL-31 | `TIMEOUT_FEASIBLE` 超过 deadline 后是否仍允许执行 | DP-13 | 高 | 已闭环：可执行但计 deadline 失败；G3 零 deadline 失败 |
| BL-32 | Web 调试模式失败后终止，还是冻结/hold 以便观察 | DP-13 | 中 | 已闭环：Web 调试可 hold_on_failure，标 diagnostic_only |
| BL-33 | 连续可行超时多少次后判定整个 run 失败 | DP-13 | 高 | 边界已闭环：连续 TIMEOUT 阈值 profile 化；超阈 run FAILED；具体次数后置 |
| BL-34 | `INVALID_INPUT` 归因于场景、Adapter 或算法的规则 | DP-13 | 中 | 已闭环：归因 SCENARIO/ADAPTER/ALGORITHM |
| BL-35 | 公共必需字段与 MPC 专项必需字段的边界 | DP-14 | 高 | 已闭环：公共必需字段 + MPC 专项必需字段分边界 |
| BL-36 | cost/constraint 公共分类词表与最小裕度表示 | DP-14 | 高 | 已闭环：与 BL-25 共享词表；最小裕度 SI 单位进 constraints |
| BL-37 | 多模态目标预测、概率和 covariance 的 trace schema | DP-14 | 中 | 已闭环：target 多模态 schema（mode/prob/trajectory/cov/source） |
| BL-38 | 长时域、多目标 trace 的体积、压缩和保留策略 | DP-14 | 中 | 已闭环：trace 分层（events 增量 + trajectory 每步 + 大 horizon 单独文件） |
| BL-39 | V1 canonical ship model/controller 参数组合 | DP-15 | 高 | 已闭环：当前 `head_on` Viknes/FLSC tuple 为唯一 canonical 候选；Rule 13/15 先修复 |
| BL-40 | 船模和控制器参数的校准精度要求 | DP-15 | 高 | 边界已闭环：reference plant 按用途回归；FCB45 实船误差门保留 `EXTERNAL_CONFIRMATION_REQUIRED` |
| BL-41 | 白盒与闭环是否必须通过相同 Adapter 代码路径 | DP-15 | 高 | 已闭环：用户确认必须相同 |
| BL-42 | 预测轨迹与闭环实际轨迹执行误差的量化方法 | DP-15 | 高 | 已闭环：solve-time 对齐执行前缀；预测误差与 Controller tracking error 分离 |
| BL-43 | Sensor 空扫描与“本步未扫描”的精确相位表示 | DP-16 | 高 | 已闭环：采用三态 `MeasurementScan`；KF truth 初始化判定为缺陷 |
| BL-44 | Planner 是否总是读取同周期最新 Tracker 输出 | DP-16 | 高 | 已闭环：基础 profile 使用同周期最新 Track |
| BL-45 | 基础 profile 即时执行计划，还是固定一周期延迟 | DP-16 | 高 | 已闭环：基础 profile 当步生效 |
| BL-46 | 非整数频率比和浮点调度容差实现 | DP-16 | 中 | 已闭环：V1 仅允许 `dt_sim` 整数倍周期；非整数多率后置 |
| BL-47 | 当前 Viknes/FLSC 参数是否足够作为 canonical plant | DP-17 | 高 | 已闭环：足够作为 synthetic reference plant；不得称数字孪生 |
| BL-48 | Custom MPC 目标船型与 Viknes 尺度/操纵性差异 | DP-17 | 高 | 边界已闭环：Viknes 结果不得外推 FCB45；后者单独 target-plant qualification |
| BL-49 | 模型失配 profile 的参数扰动范围和通过阈值 | DP-17 | 中 | 边界已闭环：V1 不加任意扰动；FCB45 range 保留 `EXTERNAL_CONFIRMATION_REQUIRED` |
| BL-50 | 控制器跟踪失败与 MPC 规划失败的归因规则 | DP-17 | 高 | 已闭环：证据驱动多标签归因；缺证据必须 `UNATTRIBUTED` |
| BL-51 | 当前 ENC 是否含可用水深/安全等深线；吃水和潮汐如何进入 | DP-18 | 高 | 边界已闭环：V1 为逐船 `chart_geometric_clearance`；operational UKC 保留外部确认 |
| BL-52 | grounding footprint、扫掠几何和时间离散容差 | DP-18 | 高 | 边界已闭环：采用 vessel footprint + interval sweep；数值容差转 BL-65/66 |
| BL-53 | collision 使用船体相交、CPA 距离或组合判定 | DP-18 | 高 | 已闭环：physical collision 只由 truth footprint/sweep 定义；风险指标分离 |
| BL-54 | goal reached 的位置、航向、速度和保持时间条件 | DP-18 | 中 | 边界已闭环：标准场景用 `route_exit`；终端状态及数值阈值转 BL-75 |
| BL-55 | 后续风流扰动 profile 的参数来源和范围 | DP-18 | 中 | 边界已闭环：V1 无扰动；PSB 仅 source reproduction；target range 保留外部确认 |
| BL-56 | 哪些运行时要求 exact，哪些允许 tolerance replay | DP-19 | 高 | 已闭环：artifact playback、exact rerun、tolerance rerun 分离；硬 verdict 不放宽 |
| BL-57 | PSB/RLMPC 并行求解器的非确定性来源和容差 | DP-19 | 高 | 边界已闭环：native 默认 tolerance-only；实测零漂移后才可晋级 exact |
| BL-58 | 当前代码中的全局 RNG 和未注入随机源 | DP-19 | 高 | 已闭环：稳定组件路径 SeedTree；禁止 global/unseeded/shared RNG |
| BL-59 | ownship 轨迹改变 Sensor 可见性时的跨算法公平性定义 | DP-19 | 高 | 已闭环：路径相关 visibility 合法；keyed CRN；God/KF 分 profile |
| BL-60 | CPU/OS/compiler 是否纳入 replay identity | DP-19 | 中 | 已闭环：runtime fingerprint 进入 replay identity |
| BL-61 | 哪些评价指标属于硬门，哪些属于评分或诊断 | DP-20 | 高 | 边界已闭环：硬门/论文评分/诊断三层分离；具体 predicate 转 BL-65..82 |
| BL-62 | 当前重建 Evaluator 与论文公式的已知偏差 | DP-20 | 高 | 已闭环：当前实现定级为 evidence-flow stub；按论文 profile/golden tables 重建 |
| BL-63 | 多项硬门的失败优先级和聚合状态 | DP-20 | 高 | 已闭环：gate 三态、qualification 四态；并发失败完整保留 |
| BL-64 | Multi-ship pairwise 规则冲突与场景级聚合方法 | DP-20 | 高 | 已闭环：无序物理 pair、有向 obligation、场景硬门合取 |
| BL-65 | 动态船体 footprint、姿态插值和安全 buffer 形式 | DP-21 | 高 | 边界已闭环：footprint 用船模 vertex（无 vertex 显式 fallback 五边形）；姿态插值连续（不得 lerp 顶点）；接触事实与 safety buffer 分离；平面须投影 UTM；具体容差后置 |
| BL-66 | 连续碰撞/搁浅扫掠检测方法与容差 | DP-21 | 高 | 边界已闭环：同步时间 CCD（禁止跨时间独立 swept union 相交）；numerical tolerance / chart uncertainty / safety buffer 三类分离；grid_size << beam；具体数值后置 |
| BL-67 | 安全域和 preferred/minimum CPA 使用固定值还是船尺度 | DP-21 | 高 | 边界已闭环：paper profile 保持固定绝对 CPA；ship-length-scaled 船域作独立 profile；缩放后不称论文复现；V1 默认 profile 待 DP-21/24 |
| BL-68 | TCPA 为负、遭遇已通过或低相对速度时的定义 | DP-21 | 中 | 已闭环：统一单一 CPA 实现（signed tcpa / future cpa / observed cpa / rel-speed status）；负 TCPA 不自动解除 encounter；低相对速度为工程决策，阈值后置 |
| BL-69 | ENC clearance 可由哪些地图层可靠计算 | DP-21 | 高 | 边界已闭环：polygon / point-line / unknown / CATZOC 四类分离；每船独立派生 hazards；不宣称 operational UKC；未测区独立报告；Skjær buffer 等细节后置 |
| BL-70 | Rule 13/14/15 分类角和边界 profile | DP-22 | 高 | 边界已闭环：oracle 为 profile-parameterized；112.5° 作 regulatory constant；head-on 半角与 contact-angle 容差作显式 profile 参数（Woerner 默认 13°/45°/10°）；采用双变量 (β,α) 分类；alternative profiles 后置 |
| BL-71 | encounter 阶段、规则锁定、解除和再次进入条件 | DP-22 | 高 | 已闭环：锁定 FSM（Eriksen 式 SF↔{OT,HO,GW,SO,EM}）；entry/exit 含 (DCPA,TCPA,t_crit) hysteresis；control state machine 与 evaluation timeline 分离；Hagen Stage 倍数标 INFERENCE |
| BL-72 | “及时、明显”和 stand-on 保向保速的量化阈值 | DP-22 | 高 | 边界已闭环：四阈值 profile（θ_detectable 2°、θ_substantial 30°、Δv_substantial 0.5、t_early_factor range-fraction）；当前代码 5°/15° 偏差须裁决 |
| BL-73 | port-to-port、crossing ahead、passed clear 的几何判定 | DP-22 | 高 | 已闭环：双变量 (α,β) pose；crossing-ahead 经 stand-on 的 α；port-to-port 经 signed-sine reward；passed-clear 为合取（t_CPA<0 ∧ range increasing ∧ CPA-pose satisfied） |
| BL-74 | Multi-ship 规则冲突、非合作目标和 Rule 17 紧急阶段 | DP-22 | 高 | 边界已闭环：Rule 17 三阶段 sub-FSM；multi-ship 不发明优先级（per-pair + C_x,gw）；非合作 = S_* 阈值触发 stand-on MAY_ACT；compliance/EM 数值后置 |
| BL-75 | goal/rejoin 的位置、航向、速度和保持时间阈值 | DP-23 | 高 | 边界已闭环：route_exit/terminal_state 双模式 profile 化；具体数值后置（ship_maneuvering 笔记本重认证后查） |
| BL-76 | 不同输出控制形式下统一 tracking metric 的方法 | DP-23 | 中 | 已闭环：tracking error 统一针对闭环执行轨迹；控制努力单独报告；control_form 声明 |
| BL-77 | 不同 solver 的 iteration/objective 可比边界 | DP-23 | 中 | 边界已闭环：不横向比较；可比较 wall-clock/feasibility/violation/outcome；归一化后置 |
| BL-78 | 提前终止和未到达 run 的统计/删失方法 | DP-23 | 高 | 已闭环：collision=FAILED 非删失；timeout=右删失用 KM；不插补假 arrival；连续指标两种报告 |
| BL-79 | deadline 使用开发机、目标硬件或归一化预算 | DP-23 | 高 | 边界已闭环：wall-clock + RT-factor 双报告；硬件进 fingerprint；RT-factor 阈值后置 |
| BL-80 | G3 canonical set 每条规则的 episode 数量 | DP-24 | 高 | 边界已闭环：canonical G3 = t=2 covering array（≥16/rule family）× 3 seeds × G3-eligible cells，零硬门失败；G4 保留 range(30)+CI；具体 t/seed 数后置 |
| BL-81 | 证据失效的字段和兼容变更规则 | DP-24 | 高 | 已闭环：manifest 增 `enc_hash` + 显式 `capability_dependencies` 聚合；失效规则 = 任一成员变化；变更分类 BREAKING/COMPATIBLE/SUPERSEDED |
| BL-82 | G3 是否要求 canonical set 零失败及可行超时政策 | DP-24 | 高 | 已闭环：G3 须零硬门失败；TIMEOUT_FEASIBLE 为 G3 soft gate 非 PASS、G4 失败；NOT_EVALUATED 不能 G3 |
| BL-83 | Web 汇总一个算法多个 capability profile 等级的方式 | DP-24 | 中 | 已闭环：per-cell matrix + aggregate badge = 最小 grade + evidence drill-down；HCI 证据 UNKNOWN |
| BL-84 | 资格任务自动晋级是否需要人工审核/签名 | DP-24 | 中 | 边界已闭环：promotion 需人工审核 + audit trail；demotion 自动即时；DO-178C/ISO 26262 迁移为 recommendation；maritime 特定标准 UNKNOWN |
| BL-85 | G4 所需 seed 数和统计功效 | DP-25 | 高 | 边界已闭环：不硬编码 seed 数；precision-target on paired difference；~20-50 起始+sequential；具体 n 后置 |
| BL-86 | tuning、qualification、holdout 场景划分 | DP-25 | 高 | 已闭环：tuning/qualification/holdout 三不相交+no-look-ahead；G3 属 qualification；evaluator 在 tuning 冻结 |
| BL-87 | 失败率、删失时间和连续指标的置信区间方法 | DP-25 | 高 | 已闭环：failure-rate→Wilson；censored arrival→KM+Greenwood；paired continuous→paired-t/Wilcoxon/bootstrap；small n→descriptive+nonparametric |
| BL-88 | KF 下路径相关 Sensor 可见性的公平比较方法 | DP-25 | 中 | 已闭环：CRN 仅外生输入；不同步 visibility；keyed-CRN 标 ENGINEERING；God/KF 分 profile |
| BL-89 | 无输出 crash/timeout 在连续指标中的呈现方式 | DP-25 | 高 | 已闭环：n_attempted/completed/crashed 持久化；连续 CI 仅 completed；failure rate Wilson on attempted；绝不插补 |
| BL-90 | trajectory/events 的字段和列级 schema | DP-26 | 高 | 已闭环：trajectory/events 列级 schema + schema_version |
| BL-91 | native crash 下的增量写入、flush 和原子封存 | DP-26 | 高 | 已闭环：events append + fsync；atomic rename；crash 保留 partial |
| BL-92 | 大型 horizon/目标预测拆文件还是保留 JSONL | DP-26 | 中 | 已闭环：大 horizon 拆 per-solve 文件 + 引用；阈值 profile 化 |
| BL-93 | 内容 hash、签名和防篡改级别 | DP-26 | 中 | 已闭环：内容 hash + tamper_evident（非 tamper_proof） |
| BL-94 | legacy pickle 最小兼容范围 | DP-26 | 低 | 已闭环：V1 不支持 pickle；legacy 仅一次性迁移 |
| BL-95 | subprocess 与 container 的选择规则 | DP-27 | 高 | 已闭环：subprocess 优先；container 仅无法共存 profile |
| BL-96 | 每 run 新建 Worker，还是 session 内持久 Worker | DP-27 | 高 | 已闭环：V1 每 run 新建 Worker；持久后置 |
| BL-97 | Worker startup/reset 后的状态隔离和可重放性 | DP-27 | 高 | 已闭环：Worker reset 清空所有状态；replay 新 Worker + 同 seed |
| BL-98 | ENC geometry 和大 horizon 的 IPC 性能 | DP-27 | 中 | 边界已闭环：in-process 完整 ENC；Worker 裁剪 geometry；MessagePack/Arrow；具体编码后置 |
| BL-99 | 本地单用户 Worker 需要的最小安全限制 | DP-27 | 低 | 已闭环：无网络/无文件写/CPU-内存上限；不做鉴权 |
| BL-100 | in-process 准入所需 crash/timeout/reset 测试 | DP-28 | 高 | 已闭环：in-process 准入需 crash/timeout/reset/replay 四 probe |
| BL-101 | Python/native 依赖 lock 和 build identity 采集方法 | DP-28 | 高 | 已闭环：lockfile hash + native build_identity 进 manifest |
| BL-102 | container image digest 与本地源码身份关联 | DP-28 | 中 | 已闭环：container digest + commit 关联；无 digest 标 unreproducible |
| BL-103 | 持久 Worker 的跨 episode 状态泄漏检测 | DP-28 | 高 | 已闭环：持久 Worker 后置；启用前须泄漏 probe；V1 不启用 |
| BL-104 | IPC framing/encoding 选择及大数组传输 | DP-29 | 高 | 边界已闭环：JSON Lines framing；大数组 Arrow/shared memory；不 pickle；具体编码后置 |
| BL-105 | deadline、grace period、terminate/kill 时序 | DP-29 | 高 | 边界已闭环：SIGTERM grace → SIGKILL；crash/timeout run 失败；grace period 数值后置 |
| BL-106 | Worker 在 run 间的重建与健康检查策略 | DP-29 | 中 | 已闭环：V1 每 run 新建；startup health probe |
| BL-107 | stderr 保留大小、敏感信息清理和报告方式 | DP-29 | 中 | 已闭环：stderr 截断保留；清理敏感占位符；failure_reason 引用尾部 |
| BL-108 | request 去重和有状态 plan 的幂等边界 | DP-29 | 高 | 已闭环：唯一 request_id + solve_id；plan 不重试；幂等返回缓存 |
| BL-109 | PSB-MPC 原生 state/control layout 和 horizon 时间语义 | DP-30 | 高 | 边界已闭环：PSB native `(4,N)` `[x,y,chi,U]` col-0=current；control `u_opt`(multiplier)+`chi_opt`(offset)；native predicted_trajectory 是真实 plant_prediction；`TrajectoryMapping.psbmpc` 4→9；`v` 处理后置 |
| BL-110 | RLMPC `6xN` 状态、控制和 reference 的精确映射 | DP-30 | 高 | 边界已闭环：RLMPC native `(6,N)` `[x,y,chi,U,V,r]`；control `[Fx,Fy]`；`r=psi_dot` native 存在；`TrajectoryMapping.rlmpc` 6→9；wrapper 须先修复调 `plan()` 读 `"trajectory"` |
| BL-111 | 缺失加速度/航向等字段允许的可验证推导 | DP-30 | 高 | 已闭环：method-driven 可验证（atan2/identity，estimated=false/true+method）vs estimated（finite_diff，estimated=true+method+dt）；细化 BL-19 blanket"missing→0" |
| BL-112 | raw native payload 的证据 schema 和体积 | DP-30 | 中 | 已闭环：stock payload 小（PSB ~1-4KB 仅 3 字段，RLMPC ~5KB 10 keys）；as-returned 持久化入 algorithm_details；PSB objective/constraints 须 C++ binding 改动（flag future enhancement） |
| BL-113 | PSB/RLMPC native status 到公共状态的映射表 | DP-30 | 高 | 边界已闭环：PSB 无 INFEASIBLE 区分（C++ 零 throw/assert，UNKNOWN，统一 NUMERICAL_FAILURE）；RLMPC local enum（非 upstream）映射表；status 须扩展 wrapper 暴露 |
| BL-114 | WebSocket schema 版本兼容和字段演进规则 | DP-31 | 中 | 已闭环：schema_version + additive-only 演进；删除/重命名 bump major |
| BL-115 | 实时推送频率、背压和慢客户端政策 | DP-31 | 中 | 已闭环：降采样推送；慢客户端丢帧；断连不影响 run；重连 seq 追赶 |
| BL-116 | 当前 horizon/ENC/目标预测的大数据传输策略 | DP-31 | 中 | 已闭环：不发 raw horizon/ENC；降采样投影；REST artifact 下载 |
| BL-117 | 本地单用户是否完全不做鉴权 | DP-31 | 低 | 已闭环：本地单用户不做鉴权；绑 127.0.0.1；远程后置 token+TLS |
| BL-118 | live state 与持久化 artifact 的 seq/hash 对齐 | DP-31 | 高 | 已闭环：live seq + manifest hash；artifact 为权威；run 结束后 live 不更新 |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|---|---|---|---|---|---|---|
| [R1] | DOMAIN_EVIDENCE | CCTA 2023 仿真评价框架论文 | 高 | 高 | 高 | DP-01, DP-02, DP-20..26 |
| [R2] | DOMAIN_EVIDENCE | Safety/COLREG Evaluator 论文 | 高 | 高 | 高 | DP-20..25 |
| [R3] | PROJECT_FACT | 上游 COLAV-Simulator 主链与 `ICOLAV` | 高 | 高 | 高 | DP-01, DP-08..19 |
| [R4] | PROJECT_FACT | PSB-MPC wrapper、core 和 benchmark corpus | 高 | 高 | 高 | DP-05..07, DP-27..30 |
| [R5] | PROJECT_FACT | RLMPC 源码、依赖与求解诊断 | 高 | 高 | 高 | DP-07, DP-27..30 |
| [R6] | PROJECT_FACT | RRT-RS 静态规划职责 | 高 | 高 | 高 | DP-03 |
| [R7] | PROJECT_FACT | VIMMJIPDA Tracker 和 Adapter | 高 | 高 | 高 | DP-03 |
| [R8] | DOCUMENTED_INTENT | 当前架构和能力矩阵 | 高 | 中 | 高 | DP-01..31 |
| [R9] | PROJECT_FACT | 当前 `ICOLAV`、PlannerTrace、RunSpec/Manifest | 高 | 中 | 高 | DP-08..14, DP-19, DP-26 |
| [R10] | PROJECT_FACT | 当前 Session/Runner/Persistence/Evaluator | 高 | 中 | 高 | DP-15..26 |
| [R11] | PROJECT_FACT | 当前 capability catalog 和 legacy custom adapter | 高 | 中 | 高 | DP-04, DP-07, DP-13, DP-24 |
| [R12] | PROJECT_FACT | 官方 PSB corpus 当前 schema 实测 | 高 | 中 | 高 | DP-05 |
| [R13] | PROJECT_FACT | 当前测试基线 `39 passed, 1 skipped` | 高 | 中 | 高 | DP-01, DP-24 |
| [R14] | DOCUMENTED_INTENT | 旧范围设计日志和用户范围修订 | 高 | 中 | 高 | DP-01..04 |
| [R15] | PROJECT_FACT | 上游 `Telemetron` 到 `Viknes` 的同模型改名提交 | 高 | 高 | 高 | DP-05 |
| [R16] | PROJECT_FACT | PSB 3600 episode 迁移后 schema/dataclass 兼容性实测 | 高 | 高 | 高 | DP-05 |
| [R17] | PROJECT_FACT | 历史/当前 More og Romsdal GDB 版本、内容哈希和几何等价性实测 | 高 | 高 | 高（easy）；低（medium 缺 Agder） | DP-05 |
| [R18] | DOMAIN_EVIDENCE | Kartverket/Geonorge 当前 `Sjøkart - Dybdedata` 元数据、许可和用途边界 | 高 | 高 | 中（仓内 GDB 缺下载元数据快照） | DP-05, DP-18, DP-21 |
| [R19] | PROJECT_FACT | PSB corpus 构造、人工筛选、location 分层和全量 benchmark 语义 | 高 | 高 | 高 | DP-05, DP-24, DP-25 |
| [R20] | PROJECT_FACT | PSB nominal/constant/variable episode 配对与初始 CPA/TCPA 分布实测 | 高 | 高 | 高 | DP-05, DP-24, DP-25 |
| [R21] | DOMAIN_EVIDENCE | NIST 组合测试与 covering-array 覆盖方法 | 高 | 高 | 中（通用软件保证方法，非海事认证标准） | DP-05, DP-24 |
| [R22] | PROJECT_FACT | 当前 Viknes/FLSC 动力学、限制、场景参数和隔离阶跃响应审计 | 高 | 高 | 高（当前仿真 plant）；低（真实船校准） | DP-06, DP-15, DP-17 |
| [R23] | DOMAIN_EVIDENCE | Telemetron 实船、辨识模型和全尺寸控制试验文献；与当前 Viknes 实现的等价性边界 | 高 | 高 | 中（同尺寸证据）；低（当前参数等价性） | DP-15, DP-17 |
| [R24] | PROJECT_FACT | 当前五个标准场景的速度包线、初始遭遇几何和规则分类实测 | 高 | 高 | 高 | DP-06, DP-07, DP-15 |
| [R25] | PROJECT_FACT | capability 静态等级、碰撞 oracle 差异和历史 Evaluator profile 审计 | 高 | 高 | 高 | DP-07, DP-20, DP-21, DP-24 |
| [R26] | DOMAIN_EVIDENCE | IMO COLREG 规则文本边界与 Evaluator 阈值解释边界 | 高 | 高 | 高 | DP-07, DP-20..22 |
| [R27] | DOMAIN_EVIDENCE | NASA、ITTC、IMO 模型验证和操纵性验证指导 | 高 | 高 | 中（方法适用）；低（直接数值阈值） | DP-15, DP-17 |
| [R28] | PROJECT_FACT | A4000 当前 FCB45 Custom MPC 目标船配置、版本和参数冲突审计 | 高 | 中（项目意图高；物理参数未验证） | 高（目标系统）；低（当前 Viknes） | DP-06, DP-17 |
| [R29] | PROJECT_FACT | 当前 Simulator 单步相位、PlannerTrace 事件和 trajectory 持久化时序审计 | 高 | 高 | 高 | DP-15, DP-16, DP-17, DP-26 |
| [R30] | PROJECT_FACT | Radar/KF 扫描周期、空扫描、缓存和 Track 初始化语义实测 | 高 | 高 | 高 | DP-09, DP-16, DP-19 |
| [R31] | PROJECT_FACT | VIMMJIPDA Adapter 对无量测扫描的处理边界 | 高 | 高 | 高（后续 VIM）；中（V1 God/KF） | DP-03, DP-16 |
| [R32] | PROJECT_FACT | 当前 SB-MPC 预测模型、horizon 和 Viknes/FLSC 执行 plant 的结构失配审计 | 高 | 高 | 高 | DP-14, DP-15, DP-17 |
| [R33] | DOMAIN_EVIDENCE | 多步预测误差用于 MPC 性能监测；验证 metric 与接受阈值分离 | 高 | 高 | 中高 | DP-15, DP-17, DP-20 |
| [R34] | PROJECT_FACT | 当前 RunSpec/模型配置、故障传播、饱和和归因字段缺口审计 | 高 | 高 | 高 | DP-15, DP-17, DP-19, DP-20 |
| [R35] | PROJECT_FACT | Romsdal GDB、SeaCharts runtime layer、深度分箱和 CATZOC 丢失边界实测 | 高 | 高 | 高 | DP-18, DP-21 |
| [R36] | DOMAIN_EVIDENCE | IHO S-57 DEPARE/M_QUAL 语义与 Kartverket 深度质量/CATZOC 说明 | 高 | 高 | 中（适用数据语义；不提供本项目 UKC 数值） | DP-18, DP-21 |
| [R37] | DOMAIN_EVIDENCE | IMO A.893(21) 对吃水、可用水深、UKC、squat/heel、潮流和水流的航次规划要求 | 高 | 高 | 中（原则适用；不提供 Playground 数值 profile） | DP-18, DP-21 |
| [R38] | PROJECT_FACT | 当前碰撞、搁浅、目标到达及 Evaluator/Session 终止语义审计 | 高 | 高 | 高 | DP-18, DP-21, DP-23 |
| [R39] | PROJECT_FACT | 上游 PSB 扰动 corpus、当前 Gauss-Markov 实现和 Viknes 风流模型边界审计 | 高 | 高 | 高（上游/当前实现）；低（FCB45 target） | DP-06, DP-17, DP-18, DP-19 |
| [R40] | PROJECT_FACT | 当前 RunSpec/Manifest、Runner replay 和 Parquet hash 语义审计 | 高 | 高 | 高 | DP-19, DP-26, DP-28 |
| [R41] | PROJECT_FACT | 当前场景、Sensor、Tracker、扰动和算法 RNG 接线审计 | 高 | 高 | 高 | DP-16, DP-19, DP-25 |
| [R42] | DOMAIN_EVIDENCE | NumPy RNG 兼容政策、SeedSequence 独立流和跨 build/LAPACK 边界 | 高 | 高 | 高 | DP-19, DP-25, DP-28 |
| [R43] | PROJECT_FACT | PSB-MPC CPE seed 接口、CE 采样、公开/私有源码边界及当前 Adapter | 高 | 高（公开接口）；低（未公开 core） | 高（当前 PSB 接入） | DP-12, DP-19, DP-27..30 |
| [R44] | PROJECT_FACT | RLMPC Acados/HPIPM、warm start、solver tolerance、代码生成和确定性 action 路径 | 高 | 高 | 高（当前 RLMPC 接入）；中（未来 learned provider） | DP-12, DP-19, DP-27..30 |
| [R45] | DOMAIN_EVIDENCE | PyTorch 跨 release/platform/device 的复现边界 | 高 | 高 | 中（未来 learned RLMPC provider；当前 registry 路径不使用 Torch policy） | DP-19, DP-28 |
| [R46] | DOMAIN_EVIDENCE | Common Random Numbers 配对仿真方法和适用边界 | 高 | 高 | 高 | DP-19, DP-25 |
| [R47] | DOMAIN_EVIDENCE | SLSA build provenance 与 NumPy numeric runtime/BLAS/LAPACK 信息 | 高 | 高 | 中高 | DP-19, DP-26, DP-28 |
| [R48] | PROJECT_FACT | 当前 reconstructed Evaluator、EncounterMonitor、BatchRunner 和测试的公式、状态及聚合审计 | 高 | 高（当前实现事实） | 高 | DP-20..25 |
| [R49] | PROJECT_FACT | 历史 `evaluator.yaml`、独立 Evaluator API 和 CCTA profile | 高 | 高 | 高（历史兼容重建）；中（当前实现） | DP-20, DP-24 |
| [R50] | DOMAIN_EVIDENCE | 2024 grounding extension 的独立 grounding penalty 与 COLREG score compensation 边界 | 高 | 高 | 中高（后续 ENC profile）；中（V1 open-water） | DP-20, DP-21 |
| [R51] | DOMAIN_EVIDENCE | Tang, Kim, Manocha, C²A: Controlled Conservative Advancement for Continuous Collision Detection of Polygonal Models, ICRA 2009（UMD GAMMA `tang09.pdf`，2026-07-28 取证） | 高 | 高（A：ICRA 一作论文，CCD 奠基性，76+ 引） | 高（2D 凸多边形 CA 是 Lin/Mirtich 一脉的直接降维） | DP-21, BL-65, BL-66 |
| [R52] | DOMAIN_EVIDENCE | Shapely 2.x manual（stable，`intersects`/`touches`/`contains`/`distance`/`buffer`/`unary_union`/polygon validity/planar Cartesian 假设，2026-07-28 取证） | 高 | 高（A：官方文档） | 高（footprint oracle 的几何后端） | DP-21, BL-65, BL-66 |
| [R53] | DOMAIN_EVIDENCE | Shapely `set_precision` reference（latest，grid_size/topology collapse/`valid_output` mode，2026-07-28 取证） | 高 | 高（A：官方文档） | 高（near-touch 容差语义） | DP-21, BL-65, BL-66 |
| [R54] | DOMAIN_EVIDENCE | Kartverket/Geonorge Sjøkart-Dybdedata 产品规约 v20201001（§5.1.2 各 layer 几何/字段/可航语义，2026-07-28 取证） | 高 | 高（A：官方 SOSI/ISO 19131 产品规约） | 高（V1 ENC hazard 层选择） | DP-18, DP-21, BL-69 |
| [R55] | DOMAIN_EVIDENCE | Kartverket CATZOC（A1/A2/B/C/D/U 六类定性语义，NO+EN 页面，2026-07-28 取证） | 高 | 高（A：官方） | 高（定性类别）；中（数值精度表不在本批授权源内，需 S-52/Ch.2） | DP-18, DP-21, BL-69 |
| [R56] | DOMAIN_EVIDENCE | IMO MSC.232(82) ECDIS 性能标准（safety contour/safety depth/SENC，2026-07-28 取证）；MSC.192(79) 经核验为雷达设备标准而非 ECDIS，原始 brief 标注有误 | 高 | 高（A：IMO MSC 决议） | 高（ECDIS 不强制固定 clearance 数值） | DP-18, DP-21, BL-69 |
| [R57] | DOMAIN_EVIDENCE | IHO S-57 Appendix A Chapter 1 Ed.3.1（DEPARE/UNSARE/M_QUAL/M_COVR/DEPCNT object class 语义，2026-07-28 取证） | 高 | 高（A：IHO 标准） | 高（object class 语义）；B（CATZOC 数值属性表在 Ch.2，未取） | DP-18, DP-21, BL-69 |
| [R58] | DOMAIN_EVIDENCE | IMO MSC.192(79) Annex 34 雷达性能标准（CPA/TCPA 告警为操作员可设置阈值、无固定数值、负 TCPA 未定义，2026-07-28 取证） | 高 | 高（A：IMO MSC 决议） | 高（CPA/TCPA 阈值归属） | DP-21, BL-67, BL-68 |
| [R59] | DOMAIN_EVIDENCE | Namgung, "Local Route Planning for Collision Avoidance of MASS in Compliance with COLREGs Rules," Sustainability 14(1):198, 2022（单一作者；CPA/TCPA 符号公式、负 TCPA 语义、Fujii 族船长度尺度椭圆船域，2026-07-28 取证） | 高 | 高（A：同行评审，63+ 引） | 高（公式/负 TCPA/船域）；低（低相对速度语义，论文未论及 V_r→0 奇点） | DP-21, BL-67, BL-68 |
| [R60] | DOMAIN_EVIDENCE | COLREG Rule 8(a)(d) 文本（"positive/ample time/safe distance/finally past and clear" 均为定性表述，无固定米值，2026-07-28 取证） | 高 | 高（A：条约文本） | 高（确认无法规固定阈值） | DP-21, BL-67, BL-68 |
| [R61] | DOMAIN_EVIDENCE | IMO COLREGS 1972 Convention 条约文本（Rule 8/13/14/15/16/17/18/21，verbatim，2026-07-28 取证） | 高 | 高（A：条约文本） | 高（规则定性边界） | DP-22, BL-70..74 |
| [R62] | DOMAIN_EVIDENCE | Woerner, K. "Multi-contact protocol-constrained collision avoidance for autonomous marine vehicles," MIT PhD thesis, 2016（canonical classification angles + behavioral thresholds，Algorithm 5/9/10/11/12/14/16/17，verbatim，2026-07-28 取证） | 高 | 高（A：MIT 博士论文，CCD/COLREG 量化奠基，123+ 引 via Woerner 2019） | 高（paper_compatible profile 的 angle/threshold 默认值来源） | DP-22, BL-70..74 |
| [R63] | DOMAIN_EVIDENCE | Woerner, K. et al. "Quantifying protocol evaluation for autonomous collision avoidance." Autonomous Robots, 2019, DOI 10.1007/s10514-018-9765-y（Woerner 2016 论文版，123 引，2026-07-28 取证） | 高 | 高（A：同行评审） | 高 | DP-22, BL-70..74 |
| [R64] | DOMAIN_EVIDENCE | Eriksen, Bitar, Breivik, Lekkas. "Hybrid Collision Avoidance for ASVs Compliant With COLREGs Rules 8 and 13–17." Frontiers in Robotics and AI 7:11, 2020, DOI 10.3389/frobt.2020.00011（state machine / rule lock-on / entry-exit criteria with hysteresis，verbatim，2026-07-28 取证） | 高 | 高（A：同行评审，NTNU COLAV 组） | 高（FSM 锁定与释放） | DP-22, BL-71, BL-74 |
| [R65] | DOMAIN_EVIDENCE | Hagen, Knutsen, Johansen, Brekke. "Exploration of COLREG-relevant Parameters from Historical AIS-data." Journal of Navigation, 2022（NTNU preprint torarnj.folk.ntnu.no/AIS_param_paper.pdf，使用 Woerner 分类，verbatim，2026-07-28 取证） | 高 | 高（A：同行评审） | 中高（AIS 实证支撑 Woerner 角度） | DP-22, BL-70 |
| [R66] | DOMAIN_EVIDENCE | Akdag, Fossen, Johansen. "Collaborative Collision Avoidance..." IFAC CAMS 2022（NTNU preprint，明确声明使用 Woerner 2016 阈值，verbatim，2026-07-28 取证） | 高 | 高（A：IFAC 同行评审） | 中高（多船协作参考） | DP-22, BL-70, BL-74 |
| [R67] | DOMAIN_EVIDENCE | Murray, B.; Naeem, W. "Stochastic COLREGs Evaluation under Uncertainty." arXiv:2402.05662, 2024（classification angle Eq.11 verbatim，引用 Hagen 2023，2026-07-28 取证） | 高 | 中（B：preprint） | 中（扩展而非定义 profile） | DP-22, BL-70 |
| [R68] | DOMAIN_EVIDENCE | Zhao, L.; Roh, M.-I. "COLREGs-compliant multiship collision avoidance based on DRL." Ocean Engineering 191:106436, 2019（仅摘要，付费墙，2026-07-28 取证） | 低（仅摘要） | 高（A：同行评审，273 引） | 低（控制器策略，非 evaluation rule） | DP-22, BL-74 |
| [R69] | DOMAIN_EVIDENCE | RTCA DO-178C / DO-330 "Software Considerations in Airborne Systems and Equipment Qualification" + "Software Tool Qualification Considerations"（verification independence、TQL-1..5，2026-07-28 取证） | 中（经二手摘要，未取全文） | 高（A：航空安全标准） | 中（安全级软件 V&V 原则可迁移；非海事强制） | DP-24, BL-84 |
| [R70] | DOMAIN_EVIDENCE | ISO 26262 Part 8 §11 "Tool Confidence Level (TCL) and Tool error Detection (TD)"（TD1/2/3、人工审核作为 TD 机制，2026-07-28 取证） | 中（经二手摘要） | 高（A：汽车功能安全标准） | 中（TCL/TD 原则可迁移；非海事强制） | DP-24, BL-84 |
| [R71] | DOMAIN_EVIDENCE | IEC 61508 Part 3 "Functional safety of electrical/electronic/programmable electronic safety-related systems - Software requirements"（通用功能安全软件 V&V，2026-07-28 取证） | 中（经二手摘要） | 高（A：功能安全基础标准） | 中（通用原则；非海事特定） | DP-24, BL-84 |
| [R72] | DOMAIN_EVIDENCE | Beiranvand, V.; Hare, W.; Lucet, Y. "Best Practices for Comparing Optimization Algorithms." Optimization and Engineering 18(4):815-848, 2017, DOI 10.1007/s11081-017-9366-2（wall-clock 依赖语言/硬件；建议 function-evaluation / normalized budget，2026-07-28 取证） | 高 | 高（A：同行评审） | 高（solver 公平比较方法） | DP-23, BL-77, BL-79 |
| [R73] | DOMAIN_EVIDENCE | Eriksen, B.-O. H. et al. 中层 NLP-MPC 论文（IPOPT solve time 在命名硬件 2.8 GHz Core i7；"Guaranteeing a maximum computational time for NLPs is difficult"，2026-07-28 取证） | 高 | 高（A：同行评审，NTNU COLAV 组） | 高（NLP solver timing 现实约束） | DP-23, BL-79 |
| [R74] | DOMAIN_EVIDENCE | Kaplan, E. L.; Meier, P. "Nonparametric Estimation from Incomplete Observations." JASA 53(282):457-481, 1958, DOI 10.1080/01621459.1958.10501452（product-limit estimator + Greenwood variance，右删失 arrival-time 分布，2026-07-28 取证） | 高 | 高（A：同行评审，统计奠基） | 高（censored arrival-time 统计） | DP-23, DP-25, BL-78, BL-87 |
| [R75] | DOMAIN_EVIDENCE | Koehler, E.; Brown, E.; Lalande, S. J. P. "On the Assessment of Monte Carlo Error in Simulation-Based Research." The American Statistician 63(2):155-162, 2009（无通用固定 replication 数；MCE 依赖设计与目标量，2026-07-28 取证） | 高 | 高（A：同行评审） | 高（seed count 方法论） | DP-25, BL-85 |
| [R76] | DOMAIN_EVIDENCE | Wilson, E. B. "Probable Inference, the Law of Succession, and Statistical Inference." JASA 22(158):209-212, 1927, DOI 10.1080/01621459.1927.10502953（Wilson score interval，小 n 比例 CI 优于 Wald，2026-07-28 取证经 NIST/SEMATECH §7.2.4.1） | 高 | 高（A：统计奠基） | 高（failure-rate CI） | DP-25, BL-87 |
| [R77] | DOMAIN_EVIDENCE | Efron, B. "Bootstrap Methods: Another Look at the Jackknife." Annals of Statistics 7(1):1-26, 1979, DOI 10.1214/aos/1176344552（bootstrap CI 三步法，distribution-free，2026-07-28 取证） | 高 | 高（A：同行评审，bootstrap 奠基） | 高（paired difference CI） | DP-25, BL-87 |
| [R78] | DOMAIN_EVIDENCE | Wilcoxon, F. "Individual Comparisons by Ranking Methods." Biometrics Bulletin 1(6):80-83, 1945, DOI 10.2307/3001968（signed-rank test，配对非参数比较，2026-07-28 取证） | 高 | 高（A：统计奠基） | 高（paired continuous metric） | DP-25, BL-87 |
| [R79] | DOMAIN_EVIDENCE | Little, R. J. A.; Rubin, D. B. "Statistical Analysis with Missing Data." 3rd ed., Wiley, 2020, Ch.1 §1.3（MCAR/MAR/MNAR 定义；complete-case analysis "generally inappropriate"，2026-07-28 取证） | 高 | 高（A：教科书权威） | 高（crash/timeout missing-data 处理） | DP-25, BL-89 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|---|---|---|---|
| SC-01 | Custom MPC 白盒固定输入 | 固定 ownship/track/ENC/reference；检查预测、约束、代价、状态、耗时 | DP-08..14 |
| SC-02 | Rule 14 对遇 | Nominal 风险基线；算法及时明显右转；安全通过 | DP-06, DP-21..24 |
| SC-03 | Rule 15/16 交叉让路 | 不从目标船前方穿越；动作及时明显 | DP-06, DP-21..24 |
| SC-04 | Rule 15/17 交叉直航 | 风险可控时保持航向航速；必要时执行 Rule 17 动作 | DP-06, DP-21..24 |
| SC-05 | Rule 13 追越 | 正确角色、充分净空、通过后恢复名义航线 | DP-06, DP-21..24 |
| SC-06 | 多船冲突 | 同时目标、无碰撞、规则行为和求解状态可解释 | DP-06, DP-21..25 |
| SC-07 | ENC 受限水域 | 动态避碰不能以搁浅或越出安全水域换取船间净空 | DP-06, DP-18, DP-21 |
| SC-08 | deadline/不可行/native crash | 结构化失败、无静默 fallback、服务进程存活、失败样本保留 | DP-13, DP-24..30 |
| SC-09 | 论文结果比对 | 仅对应算法达到 G3 后启用；冻结 episode/map/evaluator profile | DP-02, DP-25 |
| SC-10 | 旧 PSB episode 迁移核验 | raw YAML、normalized episode、migration report 三件套；状态、航线、船模和地图引用逐字段核验 | DP-05 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|---|---|---|---|---|---|
| VR-01 | DP-01 | 一个动态 MPC 验证主链；不复制 MASS-L3 TDL | 采纳 | 用户明确 Playground 是独立验证器 | Step1 前置确认 |
| VR-02 | DP-02 | 论文复现后置；算法未达到 G3 时不投入数值复现 | 采纳 | 只有可运行算法才有论文对比意义 | Step1 前置确认 |
| VR-03 | DP-03 | RRT/VIM 为可选插件，不阻塞 Custom MPC | 采纳 | RRT 是静态规划；VIM 属感知鲁棒性阶段 | Step1 前置确认 |
| VR-04 | DP-04 | `Custom MPC` 为用户自研 MPC；只经统一 Adapter 接入 | 采纳 | 避免 `Self-MPC` 命名歧义 | Step1 前置确认 |
| VR-05 | DP-05 | V1 认证当前五类标准场景 + PSB 迁移小型固定样本（easy 窗口毫米级等价）；raw/normalized/migration 三件套 | 采纳 | 主链可继续；批量迁移须逐字段核验 | Step4 批1 确认 |
| VR-06 | DP-06 | V1 四类双船 open-water + God + Viknes + 无风流；V2 ENC+KF；V3 multi-ship | 采纳 | 范围聚焦；crossing 速度超限须先修 | Step4 批1 确认 |
| VR-07 | DP-07 | Nominal→VO/SB→Custom→PSB/RL 条件；每类至少一 G3 对照 | 采纳 | 避免运行时问题遮蔽主线 | Step4 批1 确认 |
| VR-08 | DP-08 | `CustomMPCAdapter(ICOLAV)` 薄适配器；typed PlannerInput DTO；legacy 不作正式接口 | 采纳 | executed identity 可证 | Step4 批1 确认 |
| VR-09 | DP-09 | Adapter 验证坐标/单位/age/PSD/shape；缺失→INVALID_INPUT；in-process 完整 ENC | 采纳 | 防"求解成功但物理错误" | Step4 批1 确认 |
| VR-10 | DP-10 | `9xN` col-0=solve-time；selected_command 单独；StateMapping 版本化；连续性检查 | 采纳 | 时间对齐 + 连续性 | Step4 批1 确认 |
| VR-11 | DP-11 | AlgorithmDescriptor 12 强制字段 + build_identity；静态冻结/动态绑 solve_id | 采纳 | config 漂移可追溯 | Step4 批1 确认 |
| VR-12 | DP-12 | 多率调度；solve 在 t=0；hold 保留 horizon 原点；离线可关 deadline 标 diagnostic_only | 采纳 | 防伪 solve_id / 错误重放 | Step4 批2 确认 |
| VR-13 | DP-13 | strict_no_fallback；六态分类；TIMEOUT_FEASIBLE 计 deadline；INVALID_INPUT 归因三源 | 采纳 | executed identity + 失败率可信 | Step4 批2 确认 |
| VR-14 | DP-14 | 真实 solve 才写 events；公共 9+专项 4 字段；多模态 target schema；大 horizon 拆文件 | 采纳 | 可归因 + 可审计 | Step4 批2 确认 |
| VR-15 | DP-15 | 白盒+闭环走同 Adapter；canonical Viknes tuple；reference plant 按用途验收 | 采纳 | 无循环验证 / 假通过 | Step4 批2 确认 |
| VR-16 | DP-16 | 统一 sim clock；三态 MeasurementScan；V1 整数比周期 | 采纳 | 时间一致 + 公平比较 | Step4 批2 确认 |
| VR-17 | DP-17 | V1 nominal_reference（不伪造扰动）；多标签归因；Viknes 不外推 FCB45 | 采纳 | 诚实模型失配边界 | Step4 批2 确认 |
| VR-18 | DP-18 | 同 ENC source + enc_hash；footprint+sweep；route_exit/terminal_state；每船独立 hazards；只声明 chart_geometric_clearance | 采纳 | 防 Point-in-Polygon 漏报 | Step4 批2 确认 |
| VR-19 | DP-19 | artifact playback/exact/tolerance 三模式；SeedTree 稳定路径；runtime fingerprint；native 默认 tolerance-only | 采纳 | 硬 verdict 永不放宽 | Step4 批3 确认 |
| VR-20 | DP-20 | 硬门/评分/诊断三层分离；score 不抵消硬失败；reconstructed evaluator 定 evidence-flow stub；gate 三态+qual 四态 | 采纳 | 独立评价可信 | Step4 批3 确认 |
| VR-21 | DP-21 | footprint+同步 CCD 定义 collision/grounding；三类 buffer 分离；统一 CPA；ENC 四类分离；每船独立 hazards | 采纳 | 物理事实基础正确 | Step4 批3 确认 |
| VR-22 | DP-22 | profile-parameterized；锁定 FSM；双变量(β,α)；四阈值；signed-sine pose；Rule 17 三阶段；不发明 multi-ship 优先级 | 采纳 | COLREG 评价可追溯 | Step4 批3 确认 |
| VR-23 | DP-23 | 任务/执行/求解三组；objective 不横向比较；tracking 对闭环轨迹；collision=FAILED；timeout=KM；RT-factor 双报告 | 采纳 | 指标分组不掩盖硬失败 | Step4 批3 确认 |
| VR-24 | DP-24 | 组合证据；canonical=t=2 covering×3 seeds×零硬门；capability_dependencies hash；promotion 人工+demotion 自动 | 采纳 | 能力等级随漂移失效 | Step4 批3 确认 |
| VR-25 | DP-25 | 不硬编码 seed；precision-target；三不相交；Wilson/KM/paired-t/Wilcoxon/bootstrap；CRN 仅外生；绝不插补 | 采纳 | 统计结论可信 | Step4 批3 确认 |
| VR-26 | DP-26 | 六件包；增量写+原子封存；列级 schema；大 horizon 拆文件；tamper_evident | 采纳 | native crash 证据完整 | Step4 批3 确认 |
| VR-27 | DP-27 | subprocess 优先；每 run 新建；reset 清空；裁剪 geometry IPC；无网络/无写/CPU-mem 上限 | 采纳 | native abort 不影响主进程 | Step4 批4 确认 |
| VR-28 | DP-28 | 四 probe 准入；lockfile hash + build_identity；container digest；持久后置 | 采纳 | 执行模式属 runtime profile | Step4 批4 确认 |
| VR-29 | DP-29 | JSON Lines framing；SIGTERM→SIGKILL；唯一 request_id 不重试；幂等缓存 | 采纳 | 可靠通信 + 不重复更新 | Step4 批4 确认 |
| VR-30 | DP-30 | 版本化 TrajectoryMapping/StatusMapping；PSB(4,N) plant_prediction；RLMPC(6,N) r=psi_dot；method-driven；as-returned；PSB 无 INFEASIBLE | 采纳 | native 保留 + 归一化可追溯 | Step4 批4 确认 |
| VR-31 | DP-31 | 版本化投影；additive-only；降采样推送；不发 raw；127.0.0.1；live seq+hash | 采纳 | Web 只读不重算 | Step4 批4 确认 |

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|---|---|---|---|
| ALT-01 | 在本项目重建完整 TDL 三层系统 | 扩大范围，重新引入本项目要隔离的模块耦合 | DP-01 |
| ALT-02 | 论文复现、动态 Playground、RRT/VIM 三条链同优先级推进 | 分散主目标；不可用算法上提前投入复现 | DP-02, DP-03 |
| ALT-03 | 将 RRT 作为 Rule 14 动态避碰算法比较 | RRT-RS 不接收动态目标/COLREG 状态 | DP-03 |
| ALT-04 | 将 legacy `custom_mpc_adapter.py` fallback 路径视为 Custom MPC 正式接口 | 存在硬编码和静默替代，无法证明 executed identity | DP-04, DP-13 |
| ALT-05 | DP-08 方案 B：新独立接口替代 ICOLAV | 重写全部 wrapper + 破坏上游兼容，无证据收益 | DP-08 |
| ALT-06 | DP-08 方案 C：hybrid ICOLAV + Custom fast-path | 双路径一致性维护负担，fast-path 收益未证 | DP-08 |
| ALT-07 | DP-21 方案 B：自适应姿态细分（无 first-TOC） | Evaluator 缺 first-TOC 信号；细分收敛依赖上界估计 | DP-21 |
| ALT-08 | DP-21 方案 C：简化线性上界（max vertex displacement） | 过保守误报影响公正性 / 忽略旋转项则漏报 | DP-21 |
| ALT-09 | DP-22 方案 B：Eriksen FSM + 宽角度（无 Woerner pose/timely） | 缝 timely/pose/crossing-ahead，技术分解不完整 | DP-22 |
| ALT-10 | DP-22 方案 C：Murray 窄角度简化（仅分类） | 残缺方案（缺阶段/通过侧/Rule 17/multi-ship） | DP-22 |
| ALT-11 | DP-24 方案 B：全量 PSB benchmark（每 stratum 100） | 运行成本高 + schema 迁移风险 + 地理偏 PSB corpus | DP-24 |
| ALT-12 | DP-24 方案 C：缩减固定集（经验拍 N 无 covering-array 论证） | 覆盖不可量化；无方法论支撑 | DP-24 |
| ALT-13 | DP-30 方案 B：统一 `v:=U*sin(chi)`（注入虚拟 sway） | 污染 PSB plant_prediction 语义；native 不存在 sway | DP-30 |
| ALT-14 | DP-30 方案 C：PSB 不映射到 9D（保留 native 4D） | PSB 永远 G2 无法与其他算法 G3 比较 | DP-30 |
| ALT-15 | DP-19 方案 B：单一 file-hash replay（当前实现） | 混合编码噪声，无法定位漂移 | DP-19 |
| ALT-16 | DP-19 方案 C：全 exact（要求所有 run bit-exact） | native solver 跨 runtime 不可 bit-exact | DP-19 |
| ALT-17 | DP-25 方案 B：固定 30 seed + Wald CI + 完整案例 | 无功效论证 + Wald 小 n 近 0 失败 + 幸存者偏差 | DP-25 |
| ALT-18 | DP-25 方案 C：纯描述性（无 CI） | 无法量化不确定性/做配对比较 | DP-25 |

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|---|---|---|---|---|---|---|
| - | Step6 后登记 | - | - | - | - | - |

---

## 参考文献

- [R1] Tengesdal, T.; Johansen, T. A. “Simulation Framework and Software Environment for Evaluating Automatic Ship Collision Avoidance Algorithms.” CCTA 2023, DOI 10.1109/CCTA54093.2023.10252863；本地 `paper/Simulation_Framework_and_Software_Environment_for_Evaluating_Automatic_Ship_Collision_Avoidance_Algorithms.pdf`。
- [R2] Hagen, I. B.; Vassbotn, O.; Skogvold, M.; Johansen, T. A.; Brekke, E. F. “Safety and COLREG evaluation for marine collision avoidance algorithms.” Ocean Engineering 288, 2023, 115991。
- [R3] `ntnu-itk-autonomous-ship-lab/colav-simulator`，commit `a385e0fcbcf7b7de3edaada35d37dd63f2b027c2`；本地 `colav_simulator/core/colav/colav_interface.py`。
- [R4] `ntnu-itk-autonomous-ship-lab/pybind_im_and_psbmpc`，commit `367dad8809424b21c013512308de2a07bd184464`；`ntnu-itk-autonomous-ship-lab/psbmpc`，commit `8b78d009d173db20af28e1a2a662417c8d893f12`。
- [R5] `ntnu-itk-autonomous-ship-lab/rlmpc`，commit `73ef4b8cc3850a7a3b007ec14d18b962d134be34`。
- [R6] `ntnu-itk-autonomous-ship-lab/rrt-rs`，commit `9a661df7acba1bead09e6540f0b3988050db37b5`。
- [R7] `ntnu-itk-autonomous-ship-lab/vimmjipda`，commit `b4a0f77ddf72dc8ffd66095418732996c14ea1eb`。
- [R8] `Design/Colav-Simulator-Architecture.md`；`Design/Algorithm-Capability-Matrix.md`。
- [R9] `colav_simulator/core/colav/diagnostics.py`；`colav_simulator/experiment/contracts.py`。
- [R10] `colav_simulator/experiment/session.py`；`runner.py`；`persistence.py`；`colav_simulator/evaluation/evaluator.py`。
- [R11] `colav_simulator/experiment/capabilities.py`；`colav_simulator/guidance/custom_mpc_adapter.py`。
- [R12] 2026-07-27 本地兼容性审计：PSB benchmark 的 3600 个生成 episode 均因旧 `model.telemetron` 字段无法通过当前 schema。
- [R13] 2026-07-27 当前工作区全量测试：`39 passed, 1 skipped`。
- [R14] `docs/superpowers/design-logs/2026-07-27-mpc-colav-simulation-validation-platform-design-log.md` 及本轮用户确认。
- [R15] `ntnu-itk-autonomous-ship-lab/colav-simulator` commit [`377bd32da950fb904e20dbd0b15b8adee83a758d`](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/commit/377bd32da950fb904e20dbd0b15b8adee83a758d)，2025-11-29，`Rename Telemetron model to Viknes`。
- [R16] 2026-07-27 本地迁移审计：3600 个 episode 将 `model.telemetron` 改名为 `model.viknes` 后全部通过当前 Cerberus schema；再移除值为 `null` 的顶层 `stochasticity`/`rl` 后，1800 个 More og Romsdal episode 全部构造为当前 `ScenarioConfig`，另 1800 个仅因缺 `Agder_utm33.gdb` 失败。
- [R17] 上游 map 历史：删除提交 [`ec7d5fb280a15c21d9ea19798b5628d50bc7a23d`](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/commit/ec7d5fb280a15c21d9ea19798b5628d50bc7a23d)，重新加入提交 [`d159c403680c2ecf5544ed88aaf2d59b6de53cef`](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/commit/d159c403680c2ecf5544ed88aaf2d59b6de53cef)；2026-07-27 本地 GDAL/Fiona/Shapely 比对记录。
- [R18] Kartverket/Geonorge，[`Sjøkart - Dybdedata`](https://data.norge.no/nb/datasets/48cc18ef-1317-3ddd-9ca4-a06d8ffa0196/sjokart-dybdedata)；当前标记 CC BY 4.0、开放许可、持续更新，并声明该数据是导航产品基础但本身不是导航产品。
- [R19] `pybind_im_and_psbmpc` commit [`d5ee0d13c022f99d6fedd55caf28bcce6f6dac64`](https://github.com/ntnu-itk-autonomous-ship-lab/pybind_im_and_psbmpc/commit/d5ee0d13c022f99d6fedd55caf28bcce6f6dac64)；`benchmarking/generate_benchmark_scenarios.py`、`test_generated_benchmark_scenarios.py`、`benchmarking_psbmpc.py`。
- [R20] `pybind_im_and_psbmpc` commit [`d47114ea395c30bb168fe988ba962d3e6161ce81`](https://github.com/ntnu-itk-autonomous-ship-lab/pybind_im_and_psbmpc/commit/d47114ea395c30bb168fe988ba962d3e6161ce81)；2026-07-27 本地 2400 对 episode 几何签名和 nominal 初始 CPA/TCPA 分布审计。
- [R21] Kuhn, R.; Kacker, R.; Lei, Y. [“Practical Combinatorial Testing.”](https://doi.org/10.6028/NIST.SP.800-142) NIST SP 800-142, 2010；Kuhn, D. R.; Kacker, R. N.; Lei, Y. [“Combinatorial Coverage Measurement.”](https://doi.org/10.6028/NIST.IR.7878) NISTIR 7878, 2012。
- [R22] 当前 `colav_simulator/core/models.py`、`controllers.py`、`simulator.py` 和 `scenarios/head_on.yaml`；上游改名提交 [`377bd32da950fb904e20dbd0b15b8adee83a758d`](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/commit/377bd32da950fb904e20dbd0b15b8adee83a758d)；2026-07-28 隔离 surge/course-step、饱和和 `dt` 敏感性审计。
- [R23] Eriksen, B.-O. H.; Wilthil, E. F.; Flåten, A. L.; Brekke, E. F.; Breivik, M. [“Radar-based maritime collision avoidance using dynamic window.”](https://torarnj.folk.ntnu.no/Oceans17_Paper_Final_A.pdf) OCEANS 2017；[“Modeling, Identification and Control of High-Speed ASVs.”](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2479484) NTNU 2017；[“Hybrid Collision Avoidance for ASVs Compliant With COLREGs Rules 8 and 13–17.”](https://pmc.ncbi.nlm.nih.gov/articles/PMC7805726/)。
- [R24] 当前 `scenarios/head_on.yaml`、`crossing_give_way.yaml`、`crossing_stand_on.yaml`、`overtaking.yaml`、`overtaken.yaml` 与 `colav_simulator/evaluation/encounter.py`；2026-07-28 初始 CPA/TCPA、模型速度限制和分类结果审计。
- [R25] 当前 `colav_simulator/experiment/capabilities.py`、`colav_simulator/simulator.py`、`colav_simulator/evaluation/evaluator.py`；历史 [`config/evaluator.yaml`](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/blob/844718b4e5c35b31b23dfcae23ddd130ebdb55bb/config/evaluator.yaml)；2026-07-28 三算法完整重跑在 GDAL/ENC 重载阶段以退出码 139 中止，未形成新的完整证据包。
- [R26] IMO，[“Preventing collisions at sea.”](https://www.imo.org/en/ourwork/safety/pages/preventing-collisions.aspx)；Hagen et al. [“Safety and COLREG evaluation for marine collision avoidance algorithms.”](https://doi.org/10.1016/j.oceaneng.2023.115991) Ocean Engineering 288, 2023。
- [R27] NASA，[`NASA-STD-7009B`](https://standards.nasa.gov/standard/nasa/nasa-std-7009)；ITTC，[`7.5-02-06-03 Validation of Manoeuvring Simulation Models`](https://ittc.info/media/11868/75-02-06-03.pdf)，Rev. 05, 2024；IMO，[`MSC.137(76) Standards for Ship Manoeuvrability`](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.137%2876%29.pdf)。
- [R28] 2026-07-28 只读审计 A4000 `/home/marine.huang/Code/mass-l3`，branch `l3-tdl`，commit `566e2a81d1303bd4d808af376086dabf1ca1ceb4`；`config/vessels/fcb_45m.yaml` 与 `src/tactical_decision_layer/config/fcb_vessel_capability.yaml`。
- [R29] 当前 `colav_simulator/simulator.py`、`core/ship.py`、`core/colav/diagnostics.py`、`experiment/session.py` 和 `experiment/persistence.py`；2026-07-28 source-order 和持久化字段审计。
- [R30] 当前 `colav_simulator/core/sensing.py`、`core/tracking/trackers.py`、`simulator.py` 和 `scenarios/head_on.yaml`；2026-07-28 `dt=0.5/0.3/0.7 s` Radar/SB-MPC 调度实测及 KF 首 Track 初始化实测。
- [R31] `ntnu-itk-autonomous-ship-lab/vimmjipda` commit [`b4a0f77ddf72dc8ffd66095418732996c14ea1eb`](https://github.com/ntnu-itk-autonomous-ship-lab/vimmjipda/blob/b4a0f77ddf72dc8ffd66095418732996c14ea1eb/vimmjipda/vimmjipda_tracker_interface.py)；无有效量测时 Adapter 不调用底层 `manager.step()`。
- [R32] 当前 `colav_simulator/core/colav/sbmpc/sbmpc.py`、`core/colav/colav_interface.py`、`core/models.py` 和 `core/controllers.py`；2026-07-28 predictor/plant state、尺寸、动态和时间锚点审计。
- [R33] Zhao, Y.; Chu, J.; Su, H.; Huang, B. [“Multi-step Prediction Error Approach for MPC Performance Monitoring.”](https://doi.org/10.3182/20090712-4-TR-2008.00077) IFAC Proceedings Volumes 42(11), 2009；NASA [`NASA-STD-7009B`](https://standards.nasa.gov/standard/nasa/nasa-std-7009)。
- [R34] 当前 `colav_simulator/experiment/contracts.py`、`runner.py`、`core/models.py`、`core/ship.py` 和 `simulator.py`；2026-07-28 mismatch 注入能力、异常分类、输入相位和 saturation 可观测性审计。
- [R35] 当前 `data/enc/More_og_Romsdal_utm33.gdb`、`config/seacharts.yaml`、`colav_simulator/common/map_functions.py` 和 SeaCharts runtime；2026-07-28 用 GDAL/Fiona/Shapely 审计 GDB layer、`head_on` 窗口和 runtime geometry。
- [R36] IHO, [S-57 Appendix A, Chapter 1, Edition 3.1](https://legacy.iho.int/iho_pubs/standard/S-57Ed3.1/31ApAch1.pdf), DEPARE/M_QUAL；Kartverket, [Sjøkart - Dybdedata product specification 20201001](https://register.geonorge.no/data/documents/Produktspesifikasjoner_sjokart-dybdedata_v2_produktspesifikasjon-kartverket-dybdedata-20201001_.pdf) 与 [Data quality in Norwegian nautical charts](https://www.kartverket.no/en/at-sea/more-about-nautical-charts/data-quality-in-norwegian-nautical-charts-catzoc)。
- [R37] IMO, [Resolution A.893(21), Guidelines for Voyage Planning](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/AssemblyDocuments/A.893%2821%29.pdf), 1999, pp. 2-4。
- [R38] 当前 `colav_simulator/simulator.py`、`common/map_functions.py`、`common/vessel_data.py`、`evaluation/evaluator.py`、`experiment/session.py` 和 `core/guidances.py`；2026-07-28 collision/grounding/goal predicate、时间相位及异常吞没审计。
- [R39] `pybind_im_and_psbmpc/benchmarking/generate_new_disturbance_scenarios.py` 与冻结 constant/variable disturbance corpus；当前 `core/stochasticity.py`、`core/models.py` 和 disturbance 场景；2026-07-28 参数来源、随机流和物理模型边界审计。
- [R40] 当前 `colav_simulator/experiment/contracts.py`、`runner.py`、`persistence.py` 和 `integrations/registry.py`；2026-07-28 replay mode、artifact hash 和 runtime identity 审计。
- [R41] 当前 `colav_simulator/scenario_generator.py`、`behavior_generator.py`、`core/sensing.py`、`core/stochasticity.py`、`core/ship.py`、`simulator.py`、`experiment/runner.py` 和 `integrations/*.py`；2026-07-28 RNG 所有权、接线和条件抽样审计。
- [R42] NumPy, [NEP 19 - Random number generator policy](https://numpy.org/neps/nep-0019-rng-policy.html)；[Parallel random number generation](https://numpy.org/doc/stable/reference/random/parallel.html)。
- [R43] `ntnu-itk-autonomous-ship-lab/pybind_im_and_psbmpc` commit `367dad8809424b21c013512308de2a07bd184464` 的 `PSBMPC_interface.cpp`、`configs/psbmpc.yaml`、CMake/submodule 声明；当前 `colav_simulator/integrations/psbmpc.py`；2026-07-28 seed、采样和公开实现边界审计。
- [R44] `ntnu-itk-autonomous-ship-lab/rlmpc` commit `73ef4b8cc3850a7a3b007ec14d18b962d134be34` 的 `rlmpc_cas.py`、`action.py`、`config/rlmpc.yaml`、`mpc/mid_level/acados_mpc.py` 和 `uv.lock`；当前 `integrations/registry.py`。
- [R45] PyTorch, [Reproducibility](https://docs.pytorch.org/docs/stable/notes/randomness), updated 2025-10-03。
- [R46] Ehrlichman, S. M. T.; Henderson, S. G. [“Comparing Two Systems: Beyond Common Random Numbers.”](https://informs-sim.org/wsc08papers/027.pdf) Proceedings of the 2008 Winter Simulation Conference, pp. 245-251。
- [R47] SLSA, [Provenance v1.0](https://slsa.dev/spec/v1.0/provenance)；NumPy, [`numpy.show_runtime`](https://numpy.org/doc/stable/reference/generated/numpy.show_runtime.html)。
- [R48] 当前 `colav_simulator/evaluation/evaluator.py`、`evaluation/encounter.py`、`experiment/batch.py`、`tests/test_evaluator.py` 和 `tests/test_experiment_contracts.py`；2026-07-28 公式、配对方向、阶段、异常、批量状态和统计分母审计。
- [R49] 上游历史 [`config/evaluator.yaml`](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/blob/844718b4e5c35b31b23dfcae23ddd130ebdb55bb/config/evaluator.yaml) 与 [`tests/test_simulation_and_evaluation.py`](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/blob/844718b4e5c35b31b23dfcae23ddd130ebdb55bb/tests/test_simulation_and_evaluation.py)，commit `844718b4e5c35b31b23dfcae23ddd130ebdb55bb`。
- [R50] Hagen, I. B.; Murvold, M. N.; Johansen, T. A.; Brekke, E. F. [“Grounding hazard considerations in evaluation of COLREGS collision avoidance algorithms.”](https://doi.org/10.1016/j.oceaneng.2024.118204) Ocean Engineering 308, 2024, 118204；[NTNU Open publisher PDF](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3175943)。
- [R51] Tang, M.; Kim, Y. J.; Manocha, D. [“C²A: Controlled Conservative Advancement for Continuous Collision Detection of Polygonal Models,”](http://gamma-web.iacs.umd.edu/papers/documents/articles/2009/tang09.pdf) IEEE ICRA 2009；[Ewha 镜像](https://graphics.ewha.ac.kr/c2a/C2A.pdf)。2026-07-28 取证。注意：该 PDF 在上游 URL 即为 C²A 论文，与任务描述中提及的另一篇 Tang/Manocha 2009 "Interactive Continuous CCD between Deformable Models using Connectivity-Based Culling" 为不同论文；本批采用 C²A（连续碰撞检测 / first time of contact / conservative advancement 的奠基性原始论文），符合 BL-65/66 调研需求。
- [R52] Shapely, [“The Shapely v2.x Manual” (stable)](https://shapely.readthedocs.io/en/stable/manual.html)。2026-07-28 取证。
- [R53] Shapely, [`shapely.set_precision` reference (latest)](https://shapely.readthedocs.io/en/latest/reference/shapely.set_precision.html)。2026-07-28 取证。
- [R54] Kartverket/Geonorge, [“Sjøkart – Dybdedata” produktspesifikasjon v20201001](https://register.geonorge.no/register/versjoner/produktspesifikasjoner/kartverket/sjokart-dybdedata)；[111页 PDF](https://register.geonorge.no/data/documents/Produktspesifikasjoner_sjokart-dybdedata_v2_produktspesifikasjon-kartverket-dybdedata-20201001_.pdf)；[objektkatalog 镜像](https://objektkatalog.geonorge.no/Pakke/Index/EAPK_BBE76DD8_33C1_421a_A67F_14822DA42B91)。2026-07-28 取证。
- [R55] Kartverket, [“Kartkvalitet CATZOC” (NO)](https://www.kartverket.no/til-sjos/sjokart/kartkvalitet-catzoc) 与 [“Data quality in Norwegian nautical charts – CATZOC” (EN)](https://www.kartverket.no/en/at-sea/more-about-nautical-charts/data-quality-in-norwegian-nautical-charts-catzoc)。2026-07-28 取证。注意：定量位置/深度精度表（A1: ±5m/±0.5+1%d 等）不在 Kartverket 页面，而在 IHO S-52 Presentation Library APP2 / S-57 Appendix A Chapter 2 属性字典；本批授权源不含 Ch.2，故 CATZOC 数值精度表标 `EXTERNAL_CONFIRMATION_REQUIRED`。
- [R56] IMO, [“Resolution MSC.232(82) Revised Performance Standards for Electronic Chart Display and Information Systems (ECDIS),”](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.232%2882%29.pdf) 2006。2026-07-28 取证。原始 brief 中标记为 ECDIS 标准的 MSC.192(79) 经核验为“雷达设备性能标准（Annex 34）”，不含 ENC clearance/safety contour/UKC/CATZOC 内容；该错误标注已在证据矩阵 R56/R58 中纠正。
- [R57] IHO, [S-57 Appendix A – Chapter 1, Edition 3.1 (Object Classes)](https://iho.int/uploads/user/pubs/standards/s-57/31ApAch1.pdf), 2000。2026-07-28 取证（`legacy.iho.int` 镜像 TLS 失败，改用 `iho.int` 主站同文件）。DEPARE(code 42)/UNSARE(code 154)/M_QUAL(code 308)/M_COVR(code 302)/DEPCNT(code 43) object class 定义与属性集。
- [R58] IMO, [“Resolution MSC.192(79) Adoption of the Revised Performance Standards for Radar Equipment (Annex 34),”](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.192%2879%29.pdf) 2004。2026-07-28 取证。§5.29.1/§5.29.2 与 CPA/TCPA/dangerous target 定义：CPA/TCPA 限值为操作员设置，标准未给固定数值；负 TCPA 未定义。
- [R59] Namgung, H. [“Local Route Planning for Collision Avoidance of Maritime Autonomous Surface Ships in Compliance with COLREGs Rules,”](https://doi.org/10.3390/su14010198) Sustainability 14(1):198, 2022（单一作者；MDPI 直连在该网络 403，经 Wayback Machine 快照取证）。2026-07-28 取证。§2.1 Eq.1–5（CPA/TCPA 符号公式与负 TCPA 语义）、§2.3 Eq.7–13（Fujii 族船长度尺度椭圆船域及其 Namgung&Kim 2021 速度自适应扩展）。注意：原 brief 描述的“Namgung et al. 2022 'Ship Domain-Based Collision Risk Assessment for MASS'”标题与作者数有误；实际为单作者 Namgung 且标题为 Route Planning 论文。
- [R60] COLREG 1972 Convention, Rule 8(a)(d) verbatim 文本。2026-07-28 取证（官方 .gov 镜像 404，文本经多个独立复现源交叉核对一致）。仅用于确认 Rule 8 用“positive/in ample time/safe distance/finally past and clear”定性表述，不含固定米值。
- [R61] IMO, [COLREGS 1972 Convention treaty text](https://en.wikisource.org/wiki/International_Regulations_for_Preventing_Collisions_at_Sea)（Wikisource 复现 A.958(23) 条约文本）。2026-07-28 取证。Rule 8(a)(b)(c)(d)、13(b)(d)、14(a)(b)(c)、15、16、17(a)(i)(a)(ii)(b)(c)(d)、18、21（lights arcs 225°/112.5°/135°）verbatim。Rule 13(b) "more than 22.5 degrees abaft her beam" 是条约唯一固定角度（源于 Rule 21 灯光弧几何）。
- [R62] Woerner, K. [“Multi-contact protocol-constrained collision avoidance for autonomous marine vehicles,”](https://dspace.mit.edu/bitstreams/883b5eae-c230-44b3-95f5-9e7ec00e0ff9/download) MIT PhD thesis, 2016。2026-07-28 取证（16 MB PDF 全文 verbatim）。§3 Eq.3.15-3.19（contact angle α / relative bearing β 定义）、§4.5.1 Algorithm 5（classification，默认 αcrit_13=45°/αcrit_14=13°/αcrit_15=10°，p.145 明示 "all configurable... no prescribed value in COLREGS"）、Algorithm 9（port-to-port pose reward Eq.4.12 `R=[½(sin α+1)][½(sin β+1)]R_max`，p.155 "port-to-port = β=270°, α=−90°"）、Algorithm 11（Rule 17 in extremis）、Algorithm 12（delayed action，r_maneuver/r_detect/r_cpa）、Algorithm 14（θ_app=30° apparent course）、Algorithm 16（θ_md=2° detectable，stand-on maintain）、p.154 "30° by custom sufficient, some texts 35°"、p.163 admiralty 25% at fault。
- [R63] Woerner, K.; Benjamin, M. R.; Novitzky, M.; Leonard, J. J. [“Quantifying protocol evaluation for autonomous collision avoidance.”](https://link.springer.com/article/10.1007/s10514-018-9765-y) Autonomous Robots 43, 2019, 967-1001, DOI 10.1007/s10514-018-9765-y。2026-07-28 取证。Woerner 2016 论文版，123 引。
- [R64] Eriksen, B.-O. H.; Bitar, G.; Breivik, M.; Lekkas, A. M. [“Hybrid Collision Avoidance for ASVs Compliant With COLREGs Rules 8 and 13–17.”](https://doi.org/10.3389/frobt.2020.00011) Frontiers in Robotics and AI 7:11, 2020。2026-07-28 取证（仓内 `paper/Hybrid Collision Avoidance for ASVs Compliant With COLREGs Rules 8 and 13–17.pdf`，verbatim）。§4.2.1 state machine SF/OT/HO/GW/SO/EM，"all transitions to/from safe state"（rule lock-on）；§4.2.2 Eq.9-15 entry/exit criteria with hysteresis（`entry_i = d_CPA<d_CPA^enter ∧ t_CPA∈[lo,hi]`，`exit_i = d_CPA≥d_CPA^exit ∨ t_CPA∉[…]`）；EM entry `t_crit<t_crit^EM ∧ t_CPA>0` 仅从 GW/HO。
- [R65] Hagen, I. B.; Knutsen, V.; Johansen, T. A.; Brekke, E. F. [“Exploration of COLREG-relevant Parameters from Historical AIS-data.”](https://torarnj.folk.ntnu.no/AIS_param_paper.pdf) Journal of Navigation, 2022。2026-07-28 取证。使用 Woerner 分类 verbatim。
- [R66] Akdag, B.; Fossen, T. I.; Johansen, T. A. [“Collaborative Collision Avoidance...”](https://torarnj.folk.ntnu.no/Collaborative_Collision_Avoidance_IFAC_CAMS_2022_final_version.pdf) IFAC CAMS 2022。2026-07-28 取证。明确声明使用 Woerner (2016) 阈值。
- [R67] Murray, B.; Naeem, W. [“Stochastic COLREGs Evaluation under Uncertainty.”](https://arxiv.org/abs/2402.05662) arXiv:2402.05662, 2024。2026-07-28 取证。§III-A Eq.11 classification angles（HO ±5°、OT 112.5°-247.5°、SB/PS），引用 Hagen 2023。
- [R68] Zhao, L.; Roh, M.-I. [“COLREGs-compliant multiship collision avoidance based on deep reinforcement learning.”](https://www.sciencedirect.com/science/article/abs/pii/S0029801819305840) Ocean Engineering 191:106436, 2019, DOI 10.1016/j.oceaneng.2019.106436。2026-07-28 取证（仅摘要可达，全文付费墙）。多船优先级 DRL 控制器策略，非 evaluation rule，非 COLREGS 文本。
- [R69] RTCA, [DO-178C “Software Considerations in Airborne Systems and Equipment Qualification”](https://www.rtca.org/)（2011）与 [DO-330 “Software Tool Qualification Considerations”](https://www.rtca.org/)（2011）。2026-07-28 取证（经 AdaCore/Rapita 二手摘要，未取全文）。§6 要求 verification 由独立于开发者的人员执行；DO-330 定义 TQL-1..5 工具鉴定等级——若欲跳过人工验证则须鉴定自动化工具。
- [R70] ISO, [26262:2018 “Road vehicles — Functional safety,” Part 8 §11 “Qualification of software tools”](https://www.iso.org/standard/68387.html)。2026-07-28 取证（经 Embitel/Siemens Verification Horizons 二手摘要）。定义 Tool Confidence Level (TCL1-3) 与 Tool error Detection (TD1/2/3)；高 TD（人工审核/验证/输出检查）可降 TCL，移除人工审核则升高所需鉴定等级。
- [R71] IEC, [61508 Part 3:2010 “Functional safety of electrical/electronic/programmable electronic safety-related systems — Part 3: Software requirements”](https://webstore.iec.ch/publication/6027)。2026-07-28 取证（经二手摘要）。通用功能安全软件 V&V 基础标准。
- [R72] Beiranvand, V.; Hare, W.; Lucet, Y. [“Best practices for comparing optimization algorithms.”](https://doi.org/10.1007/s11081-017-9366-2) Optimization and Engineering 18(4):815-848, 2017。2026-07-28 取证。明确 wall-clock 时间依赖语言/硬件/编译器；建议用 function-evaluation 计数或归一化预算做公平比较；不同算法的 objective 不可直接比较除非归一化。
- [R73] Eriksen, B.-O. H.; Bitar, G.; Breivik, M.; Lekkas, A. M. 中层 NLP-MPC 论文（仓内 `paper/` 目录，NTNU COLAV 组）。2026-07-28 取证。IPOPT solve time 在命名硬件（2.8 GHz Core i7）上报告；明确"Guaranteeing a maximum computational time for NLPs is difficult"。
- [R74] Kaplan, E. L.; Meier, P. [“Nonparametric Estimation from Incomplete Observations.”](https://doi.org/10.1080/01621459.1958.10501452) JASA 53(282):457-481, 1958。2026-07-28 取证（全文 verbatim）。product-limit estimator 估计"P(t) of items whose lifetimes would exceed t ... without making any assumption about the form of P(t)"；§1 要求"the lifetime ... is independent of the potential loss time; in practice this assumption deserves careful scrutiny"。confidence band 见 Greenwood pointwise CI 与 Nair 1984 / Hall & Wellner 1980 simultaneous bands。
- [R75] Koehler, E.; Brown, E.; Lalande, S. J. P. [“On the Assessment of Monte Carlo Error in Simulation-Based Research.”](https://pmc.ncbi.nlm.nih.gov/articles/PMC3337209/) The American Statistician 63(2):155-162, 2009。2026-07-28 取证（全文 verbatim）。"it seems unlikely that a single choice for R [replications] will provide practical guidance in a broad range of simulation settings"；"the magnitude of MCE, and thus the number of replications required, depends on both the design and the target quantity of interest."
- [R76] Wilson, E. B. [“Probable Inference, the Law of Succession, and Statistical Inference.”](https://doi.org/10.1080/01621459.1927.10502953) JASA 22(158):209-212, 1927。2026-07-28 取证（经 NIST/SEMATECH e-Handbook §7.2.4.1 + Brown, Cai & DasGupta 2001 / Agresti & Coull 1998 coverage 文献）。Wilson score interval 公式 `L/U = [p̂ + z²/(2n) ∓ z·sqrt(p̂(1−p̂)/n + z²/(4n²))] / [1 + z²/n]`；NIST handbook："recommended by Brown, Cai and DasGupta (2001) and Agresti and Coull (1998)"，"worth does not strongly depend upon the value of n and/or p"，"lower limit cannot be negative"（Wald 的缺陷）。
- [R77] Efron, B. [“Bootstrap Methods: Another Look at the Jackknife.”](https://doi.org/10.1214/aos/1176344552) Annals of Statistics 7(1):1-26, 1979。2026-07-28 取证（全文 verbatim）。§2 三步法："1. Construct the sample probability distribution F̂, putting mass 1/n at each point ... 2. draw a random sample of size n from F̂ ... 3. Approximate the sampling distribution of R(X,F) by the bootstrap distribution of R*." distribution-free CI 方法。
- [R78] Wilcoxon, F. [“Individual Comparisons by Ranking Methods.”](https://doi.org/10.2307/3001968) Biometrics Bulletin 1(6):80-83, 1945。2026-07-28 取证。signed-rank test 比较两 matched sample 的 location——配对两算法设置的直接适用。
- [R79] Little, R. J. A.; Rubin, D. B. [“Statistical Analysis with Missing Data.”](https://www.wiley.com/en-us/Statistical+Analysis+with+Missing+Data%2C+3rd+Edition-p-9780410586051) 3rd ed., Wiley, 2020。2026-07-28 取证（Ch.1 §1.3 verbatim）。Definition 1.1："Missing data are unobserved values that would be meaningful for analysis if observed"；MCAR（Eq 1.1）"does not depend on the values of the data"；MAR（Eq 1.2）"depends on y_i only through the observed components"；MNAR"if the mechanism depends on y_i"；complete-case analysis "generally inappropriate because the investigator is usually interested in making inferences about the entire target population"。

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点 [2026-07-27]

- 模式判定：**重构模式**。保留现有 Simulator、ICOLAV、PlannerTrace、ExperimentRunner、Evaluator 和 Rule 14 六组合；目标为裁剪、补证和扩展，不推倒上游主链。
- 范围前提：用户已确认“一条动态 MPC Playground 主链”；论文复现、RRT、VIM 变为条件插件；`Custom MPC` 明确指用户自研算法。
- 快调来源：CCTA/Evaluator 论文；上游 COLAV-Simulator；PSB-MPC、RLMPC、RRT-RS、VIMMJIPDA 官方源码；当前架构、能力矩阵、接口和测试。
- NLM 状态：项目未配置 `.nlm/config.json`；未创建或写入 NotebookLM。
- 代码索引状态：当前会话未发现可调用 codegraph MCP；使用 `rg` 和定向源码读取完成项目扫描。
- 项目事实：
  - 上游主链和 `ICOLAV.plan(...) -> 9xN` 可继续作为唯一仿真/算法边界。
  - 当前 PlannerTrace 已覆盖公共预测和求解诊断，但算法声明、输入时间有效性、Worker 失败传输仍未冻结。
  - 当前正式 G3 仅 `head_on × VO/SB-MPC × God/KF`；capability 为静态声明，不是资格任务自动产物。
  - PSB benchmark 提供六类 3600 episode，但与当前 schema 不兼容；应迁移小型固定集，不直接宣称 G3。
  - PSB-MPC native abort 不能由 Python `try/except` 捕获；RLMPC 运行时未完整锁定；二者需要隔离 Worker 决策。
  - CCTA 论文示例主要验证仿真/Evaluator 流水线，不是 VO/SB-MPC 性能基准。
  - RRT 不处理动态目标；VIM Adapter 尚未通过跟踪质量门；二者不阻塞 Custom MPC。
- 已继承用户裁决：DP-01..DP-04；弃用方案 ALT-01..ALT-04。
- 新发现未决决策点：DP-05..DP-31。
- 技术分解：
  - TD-01 Custom MPC 插件 → DP-09..DP-14。
  - TD-02 最小闭环仿真夹具 → DP-16..DP-19。
  - TD-03 独立评价与资格认证 → DP-21..DP-26。
  - TD-04 外部算法 Worker → DP-28..DP-30。
- Step1 内部确认门：等待用户确认 DP-05..DP-31 和 TD-01..TD-04 是否覆盖完整；确认后才进入 Step2。

### Step1 · 用户确认 [2026-07-27]

- 用户确认 DP-05..DP-31 与 TD-01..TD-04 覆盖完整。
- DP-01..DP-04 作为此前已完成压力对齐的范围前提继续冻结。
- 获准进入 Step2；严格逐 DP 展示、逐 DP 确认，不批量裁决。

### Step2 · grilling 压力测试 [2026-07-27]

#### DP-05 · 场景包来源、迁移与溯源

- [专家] 冻结生成后的 episode、地图身份、源仓 SHA 和迁移版本；运行时不重新随机。[R1][R3][R4]
- [新手] YAML 文件存在不等于当前 schema、完整闭环和规则有效；上游 corpus 不能直接视为当前可用场景。
- [悲观] 批量迁移可能静默改变船模、地图、安全水域或遭遇几何，形成“数量很多、语义错误”的假覆盖。
- [建议结论] V1 先认证当前五类标准场景；PSB corpus 只迁移小型固定样本。每个迁移场景保留 raw YAML、normalized episode、migration report。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-01..BL-03。
- 新增场景：SC-10。

#### DP-06 · Playground ODD 与最小覆盖矩阵

- [专家] MPC 避碰至少覆盖 Rule 14、Rule 15/16、Rule 15/17 和 Rule 13；ENC 安全需独立于船间避碰判定。[R1][R2]
- [新手] 只跑 HO 会把固定右转误认为通用 COLREG MPC，无法验证让路、直航和追越角色。
- [悲观] 范围过窄导致几何过拟合；一次加入 AIS、Imazu、复杂感知和全部海况又会拖垮 Playground 主线。
- [建议结论] V1 为四类双船 open-water + God；V2 增加 ENC 受限版本 + KF；V3 增加 multi-ship。AIS、Imazu、VIM、极端海况和非合作目标后置。
- [用户确认] multi-ship 放在 V3，不阻塞首个 Custom MPC 双船闭环；风流扰动后置。
- 新增盲区：BL-04..BL-07；BL-06、BL-07 已由用户确认闭环。

#### DP-07 · 算法资格顺序和进入条件

- [专家] 所有对照算法需使用相同 episode、Tracker、船模和 Evaluator；导入或单步成功不构成性能基准。
- [新手] 先集成全部外部算法会让 PSB/RLMPC 运行时问题遮蔽 Playground 问题，并延迟 Custom MPC。
- [悲观] 错误身份、静默 fallback 或自然无风险 nominal 会产生不可用的比较结论。
- [建议结论] Nominal 风险基线 → VO/SB-MPC 规则对照 → Custom MPC → PSB-MPC/RLMPC 条件对照。Custom MPC 不等待外部算法、RRT 或 VIM。
- [用户确认] 每类规则至少一个 G3 对照算法；不要求 VO 和 SB-MPC 各自覆盖全部规则。
- 新增盲区：BL-08..BL-10；BL-08 已由用户确认闭环。

#### DP-08 · 统一 Custom MPC 插件契约

- [专家] 保留上游 `ICOLAV` 稳定边界；薄 Adapter 完成算法特定验证和转换。[R3][R9]
- [新手] 直接从 `Simulator.step()` 调用求解器会耦合场景、单位、失败处理和诊断。
- [悲观] 当前参数和 `9xN` 形状不能单独证明时间、单位、输入质量、执行身份或预测语义正确。
- [机制C默认最简版失效] 只实现 `plan()` 会缺少 reset、deadline、失败状态、PlannerTrace 和无 fallback 证明。
- [建议结论] 正式 Custom MPC 只经 `CustomMPCAdapter(ICOLAV)` 接入；Adapter 负责验证/转换，不实现算法策略。legacy guidance adapter 不作为正式路径。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-11..BL-13。

#### DP-09 · Custom MPC 输入语义

- [专家] 输入需同时表达状态、坐标/单位、时间有效性、来源和不确定性。[R3][R9]
- [新手] 当前 `do_list` 裸元组不能自描述状态顺序、协方差坐标系、量测时间或 Tracker 来源。
- [悲观] ENU/NED、度/弧度、过期 Track、非 PSD covariance 或错误船体尺度均可能形成“求解成功但物理错误”。
- [机制C默认最简版失效] 只检查 shape/finite 会放过陈旧数据、错误单位和 covariance 语义。
- [建议结论] 保持外部 ICOLAV 兼容；Adapter 内构造 typed `PlannerInput`。Adapter 验证结构/语义，solver 判断优化可行性；无效输入显式 `INVALID_INPUT`，不得替换为 God truth。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-14..BL-17。

#### DP-10 · Custom MPC 输出语义

- [专家] 执行参考与预测 horizon 必须区分；两者需来自同一最优解和 `solve_id`。
- [新手] `9x1` 可驱动船舶但不能证明 MPC horizon；只显示 horizon 又不能证明实际执行指令。
- [悲观] 预测、返回计划和执行指令若来自不同候选或求解周期，会形成假证据。
- [机制C默认最简版失效] 只验证 `9xN` shape/finite 会遗漏时间对齐、行语义、连续性和执行点一致性。
- [建议结论] `ICOLAV.plan()` 返回控制器兼容参考；PlannerTrace 保存同一真实求解的完整 horizon。Custom MPC 只有 `9x1` 最多 G2，完整非空 horizon 才能进入 G3。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-18..BL-21。

#### DP-11 · MPC 算法声明元数据

- [专家] 算法比较需冻结状态、控制、模型、时域、目标、约束、求解器和实现身份。
- [新手] 仅保存 YAML 不能说明字段语义、单位或构建版本。
- [悲观] 同名算法在不同 run 中改变模型、权重或约束，会污染统计和论文结论。
- [机制C默认最简版失效] 自由格式 dict 会产生字段缺失、拼写漂移、单位不明和版本不可迁移。
- [建议结论] Adapter 提供版本化、可哈希 `AlgorithmDescriptor`；manifest 保存冻结副本。动态变化进入 PlannerTrace，不强制不同 MPC 使用相同内部形式。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-22..BL-25。

#### DP-12 · `plan/reset` 生命周期与时序

- [专家] 仿真、控制、求解和 horizon 离散周期必须分开；低频 MPC 不应被仿真步强制重算。
- [新手] `dt_sim=0.1s` 不代表 MPC 必须以 10 Hz 求解。
- [悲观] 非求解步伪增 `solve_id`、重复 horizon 第一列或 reset 不完整都会产生错误执行/重放。
- [机制C默认最简版失效] “每步求解”改变算法负载；“重复上一指令”不能正确推进计划。
- [建议结论] 多率调度；真实求解才增加 `solve_id`。中间步确定性推进已选计划，`solver_executed=false`。每 episode 用独立 seed 完整 reset。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-26..BL-30。

#### DP-13 · 失败状态与 fallback 政策

- [专家] 必须区分可行超时、不可行、数值失败、输入错误和依赖缺失；失败样本保留在统计分母。
- [新手] 捕获异常后改用 nominal/上一计划，已经不再验证请求算法。
- [悲观] 静默 fallback 会把求解器崩溃统计为成功，且旧计划在新冲突中可能不安全。
- [机制C默认最简版失效] `except: return previous_plan` 破坏 executed identity、失败率和轨迹归因。
- [建议结论] 正式验证 `strict_no_fallback=true`；仅 `TIMEOUT_FEASIBLE` 可按后续政策执行当前可行解，其他失败使正式 run fail-stop。native crash 映射为 `NUMERICAL_FAILURE`。
- [用户确认] 采纳上述 grilling 结论；调试模式失败后的观察行为后续单独处理，不计正式结果。
- 新增盲区：BL-31..BL-34。

#### DP-14 · PlannerTrace 与 solve/hold 语义

- [专家] Trace 记录求解器真实输入/所选解，不由 Web 重算展示数据。
- [新手] 地图预测线需绑定具体 `solve_id`，否则不能证明算法实际使用该结果。
- [悲观] 每步重复写 horizon 会伪造求解频率；只存总目标无法解释约束风险。
- [机制C默认最简版失效] 自由格式 payload 会缺字段/混单位；hold 伪装新 solve 会污染耗时和成功率。
- [建议结论] 完整 PlannerTrace 只在真实 solve 写入 events；每步 trajectory 只引用 `solve_id` 和实际执行。公共 envelope + 算法专项 payload。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-35..BL-38。

#### DP-15 · 最小闭环仿真验证夹具

- [专家] 固定输入白盒测试和 controller/ship model 闭环缺一不可；开环可行不代表可执行。
- [新手] 只看预测轨迹无法发现控制器跟踪、船模响应或计划更新错误。
- [悲观] 第二套简化动力学会制造假通过；控制器补偿也可能掩盖 MPC 缺陷。
- [机制C默认最简版失效] 点质量/Web 简化引擎与最终 Simulator 证据不一致。
- [建议结论] 白盒直接调用正式 Adapter；闭环使用唯一 `SimulationSession`、controller 和 ship model。God 是确定性测试夹具，前端无第二引擎。
- [用户确认] 白盒与闭环必须走相同 Adapter；正式结果只来自 SimulationSession 闭环。
- 新增盲区：BL-39..BL-42；BL-41 已由用户确认闭环。

#### DP-16 · 闭环相位与多率关系

- [专家] 所有算法必须在相同时间相位读取状态、计划和执行，避免一帧延迟或未来信息。
- [新手] “每步调用”仍可能先积分后求解，使 MPC 看到未来状态。
- [悲观] truth、Tracker 和 Planner 时间不一致，或不同算法执行延迟不同，会形成不公平比较。
- [机制C默认最简版失效] 浮点取模和模块私有时钟会漏触发、漂移或重复更新。
- [建议结论] Session 持有唯一 sim clock；同一 `t` 完成环境、sensor、tracker、plan、control，再积分 `t→t+dt`。基础 profile 使用同周期最新 Track、计划当步生效；真实延迟后置。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-43..BL-46；BL-44、BL-45 已由用户确认闭环。

#### DP-17 · MPC 模型与仿真船模失配边界

- [专家] MPC 预测模型不应被强制等同于仿真 plant；闭环需验证简化模型面对真实动力学的可执行性。
- [新手] 复用同一模型代码会产生漂亮预测，但不能证明模型误差鲁棒性。
- [悲观] 完全一致形成循环验证；失配过大又会把不适用船型误判为算法缺陷。
- [机制C默认最简版失效] 无惯性运动学 plant 会高估转向、制动和避碰净空。
- [建议结论] V1 冻结现有 Viknes 3DOF + FLSC 为 canonical plant；Custom MPC 声明自己的模型。基础通过后再做参数扰动/饱和/延迟压力测试。
- [用户确认] 采纳上述 grilling 结论；结果只适用于声明的 plant/ODD，不宣称等价于实际 TDL 船型。
- 新增盲区：BL-47..BL-50。

#### DP-18 · ENC、环境与终止语义

- [专家] 算法、plant 和 Evaluator 必须引用同一 ENC 数据源；船间安全与搁浅安全分开计算。
- [新手] 地图显示正常不等于 MPC 收到 hazard；中心点安全不等于船体 footprint 安全。
- [悲观] 点船、粗时间步或未知水深会漏掉穿透、船体相交和浅水风险。
- [机制C默认最简版失效] 单步 `Point in Polygon` 检查漏掉船体、扫掠、安全裕度和浅水。
- [建议结论] 同一 ENC source 派生算法/evaluator geometry并记录 SHA。V1 无风流，使用 footprint + sweep 检查；未审计 bathymetry/潮汐前只声明 ENC hazard 几何安全。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-51..BL-55。

#### DP-19 · 确定性重放

- [专家] 场景、Sensor、Tracker、扰动和算法使用独立随机流；复现还需代码、依赖、地图和配置身份。
- [新手] 单一根 seed 会因任一模块新增采样而改变其他模块随机序列。
- [悲观] Native/GPU/并行求解器可能不 bit-exact；完全不检查又无法发现行为漂移。
- [机制C默认最简版失效] 全局 RNG/共享 seed 会让算法执行顺序影响场景和感知输入。
- [建议结论] 冻结 episode + SeedBundle + runtime identity；确定性运行用 exact replay，原生非确定性运行用声明容差。Web evidence replay 不重算算法。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-56..BL-60。

#### DP-20 · MPC 独立评价与资格认证体系

- [专家] 评价独立于被测 MPC，使用仿真 truth；硬安全失败不能被其他高分抵消。[R1][R2]
- [新手] MPC objective 只证明优化了自己的目标，不能证明安全、守规或可执行。
- [悲观] 单一加权总分可能让碰撞算法因延误小而排名更高；用 Track 评价会把估计误差当真值。
- [机制C默认最简版失效] 只查最小距离会漏掉搁浅、错误通过侧、直航船过度操纵、求解失败和未到达。
- [建议结论] 独立评价先执行数据/身份/安全/COLREG/任务/求解硬资格门；通过后才计算研究评分。Multi-ship 先 pairwise 后场景聚合。
- [用户确认] 采纳“先硬资格门，后研究评分”，不用单一总分决定可用性。
- 新增盲区：BL-61..BL-64。

#### DP-21 · 安全与 ENC Oracle

- [专家] 实际碰撞事件与安全裕度不足分开；前者由船体几何，后者由 CPA/安全域指标表达。
- [新手] 固定 30m 不能同时适配船型、事实碰撞和保守安全域。
- [悲观] 离散采样、中心距离和过期 CPA 会漏掉步间穿越、首尾相交和遭遇阶段差异。
- [机制C默认最简版失效] 单一最小中心距会让可调阈值改变“是否碰撞”的事实。
- [建议结论] truth footprint/sweep 定义 collision；ENC footprint/sweep 定义 grounding。CPA、clearance、安全域、near-miss 独立输出。G3 硬门为零 collision/grounding/map exit。
- [用户确认] 采纳事实事件与风险指标分离。
- 新增盲区：BL-65..BL-69。

#### DP-22 · COLREG 行为 Oracle

- [专家] 先识别遭遇/角色，再按阶段评价；模糊法规术语需版本化 evaluator profile。[R2]
- [新手] 每帧重分类会让算法通过自身转向逃离原规则。
- [悲观] 不锁角色会漏掉错误转向；只看最终通过侧会漏掉过晚或不明显动作。
- [机制C默认最简版失效] 最终几何不能证明 Rule 8、16、17 的时序行为。
- [建议结论] truth pairwise Encounter Oracle 锁定规则角色，按风险/阶段解除；算法内部规则状态仅作诊断。输出“符合 evaluator profile”，不直接宣称法律合规。
- [用户确认] 采纳规则角色锁定 + 分阶段行为评价。
- 新增盲区：BL-70..BL-74。

#### DP-23 · 任务、控制与求解指标

- [专家] 安全通过后仍需验证任务完成、路径恢复、控制可执行性和实时求解性能；指标分组报告。
- [新手] 无碰撞可能只是停车；到达目标也可能依赖饱和、摆动或大量超时。
- [悲观] 平均耗时隐藏 deadline 尾部；碰撞后提前终止可能获得虚假低延误。
- [机制C默认最简版失效] 综合分会掩盖未到达、饱和、不连续和严重超时。
- [建议结论] 分任务/执行/求解三组，保留原始单位；仅通过安全/COLREG 硬门的 run 参与效率排名。不同算法 objective 不横向比较。
- [用户确认] 采纳分组指标，不生成掩盖硬失败的综合性能分。
- 新增盲区：BL-75..BL-79。

#### DP-24 · G2/G3/G4 证据门

- [专家] 能力等级属于规则/场景包/算法/Tracker/配置/runtime 组合，不只属于算法名。
- [新手] 当前 `SB-MPC=G3` 实际只证明特定 head-on 组合，不代表 crossing 或其他 ODD。
- [悲观] 手工等级不会随代码、地图、依赖和配置漂移而失效。
- [机制C默认最简版失效] import 或单次无碰撞不足以排除自然净空、fallback 和无诊断。
- [建议结论] 资格任务生成 G0-G4 和证据 hash。G3 需 canonical set 硬门、可观察动作、完整 trace 和 replay；G4 再进入多 seed 统计。Nominal 仅作 G2 风险基线。
- [用户确认] 等级按组合证据生成，不再全局硬编码算法等级。
- 新增盲区：BL-80..BL-84。

#### DP-25 · 公平 episode、seed 与统计政策

- [专家] 使用相同 episode/seed/Tracker/plant/Evaluator 做配对实验，并比较配对差值。
- [新手] 不同难度场景各跑 30 次仍不可比较。
- [悲观] 删除碰撞、超时或 crash 会产生幸存者偏差；重复用验证集调参会过拟合。
- [机制C默认最简版失效] 均值隐藏长尾；失败作为缺失值会奖励不稳定算法。
- [建议结论] G3 用 deterministic canonical set；G4 用预注册 seed 和配对统计。tuning/qualification/holdout 分离，所有失败保留在分母。
- [用户确认] 采纳配对实验、失败保留和数据集隔离；seed 数/统计方法进入 Step3。
- 新增盲区：BL-85..BL-89。

#### DP-26 · 可复现实验证据包

- [专家] 同时保存输入身份、逐步执行、规划事件、评价和报告；产物带 schema version/hash。
- [新手] report 无法重算，trajectory 无法证明算法/地图/配置身份。
- [悲观] 只在正常结束写文件会丢失 native crash 证据；部分写入可能伪装完整 run。
- [机制C默认最简版失效] pickle/单体 JSON 不利于审计、迁移、增量写和安全读取。
- [建议结论] 保持 manifest、episode、trajectory、events、evaluation、report 六件包；events/trajectory 增量写，成功/失败均原子封存。Web 只读同一证据。
- [用户确认] 采纳六件证据包；失败 run 同等持久化。
- 新增盲区：BL-90..BL-94。

#### DP-27 · 外部/原生算法隔离 Worker

- [专家] native abort、依赖冲突或独立 runtime 需进程隔离；Python `try/except` 不能捕获 `SIGABRT`。
- [新手] PSB native assertion 会连同 Web/Session 服务退出。
- [悲观] 全部容器化增加无谓复杂度；完全不隔离又让一次崩溃破坏整个服务和证据。
- [机制C默认最简版失效] API 进程加载 native solver，无法可靠强杀超时或隔离依赖/全局状态。
- [建议结论] 按需隔离；兼容算法可 in-process，native/冲突算法使用本地 Worker。V1 subprocess 优先，容器只用于无法共存的 profile。
- [用户确认] 采纳按需隔离，不把所有算法微服务化。
- 新增盲区：BL-95..BL-99。

#### DP-28 · in-process/Worker 边界与运行时身份

- [专家] 隔离不能仅按语言判断；Python extension 同样可能 native abort，不可中断 solve 也需 Worker。
- [新手] import 成功不能证明 reset、deadline、状态隔离或依赖兼容。
- [悲观] 依赖升级改变 native runtime 后，旧 capability 证据可能继续误用。
- [机制C默认最简版失效] 按算法名硬编码执行模式会遗漏真实链接库和 build 差异。
- [建议结论] AlgorithmDescriptor 声明 execution profile，Registry 探测 runtime。in-process 需通过准入；native/不可取消/冲突用 subprocess；系统依赖无法复现时才用 container。
- [用户确认] 执行模式属于 runtime profile，不由算法名硬编码。
- 新增盲区：BL-100..BL-103。

#### DP-29 · Worker 通信、超时与崩溃语义

- [专家] 协议需版本化并区分 health/reset/plan/shutdown；parent 负责 hard deadline 和输出校验。
- [新手] 只读 stdout 不能区分日志、部分响应、崩溃、卡死或重复请求。
- [悲观] 自动重试有状态 plan 会重复更新；自动重启继续 run 会丢失 warm start/内部状态。
- [机制C默认最简版失效] 无 framing JSON 易被日志污染，只等进程退出无法中止卡死。
- [建议结论] 每次调用有 request_id/solve_id；plan 不自动重试。超时/crash 使当前正式 run 失败，Worker 仅为下一 run 重建。stdout 仅协议，stderr 留证。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-104..BL-108。

#### DP-30 · 外部 MPC 输出归一化

- [专家] 完整保留 native 状态/控制/诊断，再通过声明映射转为公共轨迹/trace。
- [新手] 不同维度直接补零可能把速度、航向和控制放错行。
- [悲观] 重新生成展示轨迹会脱离算法真实解，丢失 native status 会伪装成功。
- [机制C默认最简版失效] `vstack zeros` 隐藏缺失语义，单一 exception 丢失 timeout/infeasible 差别。
- [建议结论] 每个 Adapter 版本化 TrajectoryMapping/StatusMapping；先 raw、后归一化，并保存两者 hash。不能提取真实 horizon/时间网格/所选控制的外部 MPC 最多 G2。
- [用户确认] 采纳上述 grilling 结论。
- 新增盲区：BL-109..BL-113。

#### DP-31 · 后端到 Web Viewer 的只读边界

- [专家] Web 消费 Session/PlannerTrace/Evaluator/Evidence 的版本化投影，不重新实现动力学、风险或规则。
- [新手] 前端自行计算 CPA/规则标签会与离线报告产生不同结论。
- [悲观] 直接发送内部对象导致 schema 漂移；慢客户端可能阻塞仿真。
- [机制C默认最简版失效] 每步发送全部 raw horizon/ENC 会造成巨大消息、丢帧和 UI 卡顿。
- [建议结论] 后端唯一事实源；WebSocket 是可降采样实时投影，REST/artifacts 是完整证据。断连不影响 run；前端分支只负责展示。
- [用户确认] Web 为只读观察/控制端，正式评价和证据由后端生成。
- 新增盲区：BL-114..BL-118。

#### Step2 完成门

- DP-05..DP-31 均已逐项完成专家/新手/悲观压力测试并获用户确认。
- TD-01..TD-04 的全部技术子模块均已完成“默认最简版失效”追问。
- BL-01..BL-118 已登记并分配优先级；用户直接确认的范围问题已标记闭环。
- SC-01..SC-10 已登记。
- Step2 完成；未获用户授权前不进入 Step3。

### Step3 · 用户授权 [2026-07-27]

- 用户确认进入 Step3。
- 先按高优先级调研场景迁移、地图溯源和 canonical episode 证据；证据展示并获确认前，不标记相关 BL 闭环。

### Step3 · 场景迁移与地图溯源证据批次 [2026-07-27]

#### BL-01 · `telemetron` 应映射还是删除

- [R15] 上游提交直接将 `TelemetronParams`、schema key 和全部场景的 `model.telemetron` 改名为 `ViknesParams`/`model.viknes`；commit message 明示原船名一直错误。
- 改名前后 draft、length、width、船体顶点、质量/阻尼、力和速度限制等核心参数保持一致；证据指向“同一动力学模型改名”，不是移除船模。
- [R16] 3600 个 PSB episode 只做 `telemetron -> viknes` 后，全部通过当前 Cerberus schema。
- 当前 dataclass 构造另有独立兼容问题：历史保存文件包含顶层 `stochasticity: null`、`rl: null`，当前 `from_dict()` 会对 `None` 调用子配置解析。移除这两个空容器后，1800 个 More og Romsdal episode 全部构造成功；另 1800 个只被缺失的 `Agder_utm33.gdb` 阻断。
- 证据边界：字段应映射，不应删除；但完整 migration 还必须规范化空 optional container，并产生逐字段 migration report。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-02 · 历史/当前 ENC 等价性与许可

- [R17] 论文期上游仓库曾包含 `data/map/More_og_Romsdal.gdb`，2023-03-27 删除；2025-12-29 重新加入 `data/enc/More_og_Romsdal_utm33.gdb` 和 Rogaland。
- 两个 More og Romsdal 文件不是同一快照：历史版 178 文件、约 151 MiB、数据提取时间 2021-06-08；当前版 195 文件、约 193 MiB、数据提取时间 2025-08-04。排序相对路径与文件 SHA-256 清单的复合哈希分别为 `b592dbdf...62e0`、`22e9b557...f75`。全图关键 layer feature count 也不同。
- 两者 CRS、layer 集一致，均为 EPSG:25833。对 easy corpus 的固定 3 km x 3 km 窗口 `[39400, 6957400] .. [42400, 6960400]`，关键安全 layer 的空间过滤计数全部一致。
- 按当前 seacharts 的 `dybdeareal.minimumsdybde`、`grunne.dybde` 规则重建 0/1/2/5/10/20/50/100/200/350/500 m safe-area：最大 Hausdorff 距离 `0.001539 m`；最大面积差比 `3.753e-6`。因此 easy 窗口可支持毫米级几何等价，不支持“全图版本相同”表述。
- Medium corpus 引用 `Agder_utm33.gdb`；该地图不在当前仓库，也未在可见上游 map 历史中找到。Medium 1800 episode 无法完成地图等价和闭环核验。
- [R18] 当前官方 `Sjøkart - Dybdedata` 元数据标记 CC BY 4.0、开放许可、持续更新，并声明数据不是导航产品。仓库只链接 Geonorge，未保存每个 GDB 的下载 URL、元数据版本、许可快照或 attribution；历史 2021 GDB 的精确许可不能仅由仓库证明。
- 证据边界：easy 几何等价已有高置信实测；全图版本相同、Agder 等价、历史许可来源仍为 `EXTERNAL_CONFIRMATION_REQUIRED`。
- 状态：部分证据已登记，未标闭环，等待用户确认是否接受上述已知边界。

#### BL-03 · 每类 100 episode 的最小认证集

- [R19] 上游定义的是全量 benchmark，不是缩减认证集：脚本枚举目录全部 episode，再按 benchmark、traffic situation、location 求平均；没有 sampling 参数、最小数量或覆盖门。
- Corpus 为 `2 difficulty x 3 disturbance profile x 6 encounter type x 100 = 3600`。`easy` 由 2 个 location 构成，每类 `60/40`；`medium` 由 4 个 location 构成，每类 `25/25/25/25`。创建提交称 easy 为 open-sea、medium 为 constrained area。
- 生成流程固定 `n_episodes=100`、示例 `ScenarioGenerator(seed=1)`，但冻结 episode 未记录逐文件 RNG seed；另有交互脚本要求人工 accept/delete。冻结 YAML 是可追溯输入，无法仅凭现存 seed 无损再生人工筛选后的 corpus。
- [R20] constant/variable disturbance 从 nominal episode 派生。2400 对比中，地图、时序、初始状态、waypoint、speed plan 在 `1e-10` 容差内全部配对一致；可做同 geometry 的 paired comparison，不能把三份当 300 个独立 geometry。
- 初始 CPA/TCPA 分布在 location 间显著不同。例如 easy HO 的 DCPA 中位数约 `36.8/25.3 m`；medium HO 四个 location 约 `74.0/29.7/48.1/44.7 m`。部分 overtaken episode 初始 TCPA 已为负，说明仅按初始 CPA 排序不足以代表完整动态遭遇。
- [R21] NIST covering-array 方法支持按离散 factor/t-way interaction 构造较小但可量化覆盖的回归集；它不提供海事 MPC 的固定最小样本数，也不替代连续风险边界、长尾失败或统计置信验证。
- 证据边界：上游忠实 benchmark 应跑每 stratum 全 100；G3 快速 canonical set 若缩减，必须声明为本项目新建的 coverage-based regression set，不得声称等同上游 benchmark。具体最小数量在 factor、risk bin、t-way strength 和运行预算未裁决前为 `UNKNOWN`。
- 状态：证据已登记，未标闭环，等待用户确认是否接受“上游无最小集；G3 缩减规则需本项目另行裁决”。

#### 本批用户确认门

- 待用户分别确认 BL-01、BL-02、BL-03 的证据是否回答原问题。
- 未确认前不改盲区为“已闭环”，不进入 Step4。

### Step3 · 首批证据用户确认 [2026-07-28]

- 用户确认本批证据。
- BL-01 闭环：历史 `model.telemetron` 必须迁移为 `model.viknes`；删除船模不符合上游改名证据。
- BL-02 接受证据边界：easy 固定窗口可按毫米级几何等价处理；不得扩张为全图或版本完全相同。`Agder_utm33.gdb`、历史许可/下载元数据继续标记 `EXTERNAL_CONFIRMATION_REQUIRED`。
- BL-03 闭环：上游 benchmark 不存在缩减认证集；忠实运行语义为每 stratum 全 100。本项目 G3 canonical set 的具体数量和覆盖强度继续由 BL-80 调研。
- Step3 尚未完成；等待用户授权下一证据批次，不进入 Step4。

### Step3 · 第二批用户授权 [2026-07-28]

- 用户确认继续调研 V1 Playground 基础真实性。
- 本批范围：BL-04、BL-09、BL-39、BL-40、BL-47、BL-48。
- 目标：明确 V1 ODD、有效风险基线、Viknes/FLSC canonical plant、校准证据与 Custom MPC 模型失配边界。
- 证据展示并获确认前，不标记相关 BL 闭环，不进入 Step4。

### Step3 · V1 ODD、风险基线与 canonical plant 证据批次 [2026-07-28]

#### BL-04 · Custom MPC 预期船型、速度、水深和可操纵范围

- [R22] 当前唯一完整展示链 `head_on` 的实际 plant 是 Viknes/FLSC：船长 `8.45 m`、船宽 `2.71 m`、吃水 `0.5 m`、速度上限 `10 m/s`、艏摇角速度上限 `15 deg/s`；场景速度 `7 m/s`、`dt=0.5 s`、无风流。
- 当前 ENC depth 处理将吃水向上匹配可用海图深度层；未建模潮汐、UKC 和动态下沉量。因此只能证明当前海图几何层中的相对安全水域，不能证明真实航行水深裕度。
- [R28] Custom MPC 生产目标可暂识别为 `FCB45`：约 `45 m x 8 m`、吃水 `1.55 m`、质量 `145000 kg`、服务航速 `18 kn`。但 A4000 两份配置分别给出最大航速 `22/28 kn`，转向能力也冲突，并带 `HAZID-UNVERIFIED`、`TBD-HAZID` 或 preliminary 标记。
- 证据边界：V1 可定义的是“Viknes 仿真参考 ODD”，不能写成“FCB45 目标 ODD”。FCB45 速度、水深和操纵包线仍为 `EXTERNAL_CONFIRMATION_REQUIRED`。
- 状态：证据已登记，未标闭环，等待用户确认上述双 ODD 边界。

#### BL-09 · 有效风险基线与对照算法通过阈值

- [R24] `head_on` 初始距离约 `2828.43 m`、DCPA 约 `0 m`、TCPA 约 `202.03 s`，分类为 head-on；它满足“没有算法介入即存在真实风险”的基线条件。
- [R25] 当前 capability 记录的最小船距为 Nominal `7.43 m`、VO `43.36/43.70 m`、SB-MPC `94.17/91.81 m`，但这些是静态登记值，不是资格任务自动生成结果。2026-07-28 完整重跑在 GDAL/ENC 重载时退出 `139`，未产生新的完整证据包。
- 当前 collision oracle 不统一：Simulator 以本船半长 `4.225 m` 判定；重建 Evaluator 以两船半长之和 `8.45 m` 判定。因此 Nominal `7.43 m` 会出现 Simulator“未碰撞”、Evaluator“碰撞”的冲突。
- 历史 `ccta_2023_demo` profile 使用 `r_pref/r_min/r_nm/r_col = 190/100/50/30 m`。按该 profile，VO 的约 `43 m` 位于 near-miss 区间，SB-MPC 的约 `94 m` 仍低于 minimum；“无物理碰撞”不等于“达到 Evaluator 偏好安全距离”。
- [R26] COLREG Rule 8/14 要求及时、明显、留有充分水域和安全通过，但 IMO 未给全部船型通用的固定米制通过阈值；Evaluator 距离/角度是版本化研究 profile，不应冒充法规硬事实。
- 证据支持三层分离：
  - 风险资格：规则锁定、`TCPA > 0`、Nominal 存在碰撞或 profile 级不安全，排除自然净空。
  - 硬门：船体无相交、无搁浅/越界、无 fallback/crash、任务完成。
  - 评分：版本化 CPA/COLREG/Evaluator profile，不改写物理硬门。
- 证据边界：可冻结语义分层；具体 buffer、score 和 G3 数值门仍需在 DP-20..25 中结合船尺度/profile 裁决。
- 状态：证据已登记，未标闭环，等待用户确认是否接受“事实硬门与研究 profile 分离”。

#### BL-39 · V1 canonical ship model/controller 参数组合

- [R22] 当前最完整、内部一致的候选组合是 `head_on.yaml` 中冻结的 Viknes 参数、场景 FLSC 增益、饱和 RK4、`dt=0.5 s`、`7 m/s` 和无扰动环境；不能依赖可能漂移的 controller 默认增益。
- 隔离 plant 审计：
  - `7 m/s` 稳态 surge 所需约 `6965 N`，低于正向力上限 `13100 N`。
  - 最大正向力对应正稳态速度约 `9.667 m/s`，与 `10 m/s` 状态上限接近。
  - `7 m/s`、`30 deg` 航向阶跃在 `dt=0.5/0.1/0.05 s` 下均稳定；峰值约 `38.01/36.52/36.32 deg`，约 `22 s` 收敛，均触及 `15 deg/s` 艏摇速率上限。
  - `dt=0.5 s` 相比 `0.1/0.05 s` 多约 `1.5–1.7 deg` 峰值超调；可稳定运行，不足以证明时间离散误差可忽略。
- [R24] 其余标准场景不能原样并入 canonical ODD：crossing 两场景速度均为 `15 m/s`；overtaking/overtaken 至少一船 `15 m/s`，超过 Viknes `10 m/s` 上限并在积分后被钳位。当前统一分类器还把两追越场景初始状态分类为 crossing/clear。
- 证据边界：只有 Rule 14 `head_on` 已有 coherent plant tuple；Rule 13/15 场景需先修复速度和几何/分类，再谈同一 canonical plant。`dt=0.5` 是否保留为资格 profile 仍是设计裁决。
- 状态：证据已登记，未标闭环，等待用户确认候选范围。

#### BL-40 · 船模和控制器参数的校准精度要求

- [R27] NASA 要求项目按模型用途自定并批准验收标准；ITTC 要求明确目的/ODD，并用系数、力矩、标准操纵、自由航行轨迹、基准/模型/实船数据和不确定度验证。权威来源未给适用于所有 MPC Playground 的统一 `5%` 或类似误差门。
- IMO `MSC.137(76)` 强调用全尺寸试航验证预测，但适用对象主要为 `100 m` 以上、常规舵船，不能直接作为 `8.45 m` 舷外机 Viknes 或 `45 m` FCB 的数值标准。
- 因此必须区分两种 claim：
  - 验证算法逻辑：允许经过确定性回归、步长收敛和物理约束检查的 synthetic reference plant。
  - 预测实船能力：必须使用目标船专属辨识/试航数据、参数不确定度和项目批准的误差门。
- 证据边界：当前资料足够定义 reference-plant 回归要求；不足以定义 FCB45 实船转移误差，后者为 `EXTERNAL_CONFIRMATION_REQUIRED`。
- 状态：证据已登记，未标闭环，等待用户确认 claim 分级。

#### BL-47 · 当前 Viknes/FLSC 是否足够作为 canonical plant

- [R22] 当前 plant 是三自由度欠驱动模型，输入为广义力；无推进器、舵或舷外机执行机构动态。FLSC 源码也明确其单推进器/舵假设并非该船真实配置；风载系数标记为 crude guessed values。
- [R23] 公开 Telemetron 文献能证明同类 `8.45 m` 高速 ASV 曾有实船辨识和全尺寸控制试验；已发表模型是随状态变化的 2DOF speed/yaw-rate 模型。它不能证明当前常系数 3DOF、零 added mass、广义力输入的 Viknes 实现已被该试验校准。
- 上游改名说明当前参数原先错误命名为 Telemetron，进一步限制了将 Telemetron 文献直接当作当前 plant 校准证据。
- 证据结论：Viknes/FLSC 可作为 V1 synthetic canonical plant，前提是冻结完整参数并增加黑盒回归；不能称为真实 Viknes/Telemetron digital twin。
- 状态：证据已登记，未标闭环，等待用户确认用途边界。

#### BL-48 · Custom MPC 目标船型与 Viknes 尺度/操纵性差异

- [R28] 相对当前 Viknes，FCB45 长度约 `5.33x`、宽度约 `2.95x`、吃水约 `3.1x`、名义质量量级约 `36.4x`。即使服务速度与 Viknes `10 m/s` 上限接近，转弯半径、惯性、制动力、控制输入和 ENC clearance 不能继承。
- FCB45 两份 capability manifest 冲突且未完成 HAZID；当前不能构造有证据支持的 FCB45 plant，也不能用 Viknes 场景通过证明 FCB45 MPC 有效。
- 证据边界：V1 只能验证 Custom MPC Adapter、优化问题、COLREG 行为和在 reference plant 上的闭环性质；FCB45 泛化必须作为后续 target-plant profile 单独资格认证。
- 状态：证据已登记，未标闭环，等待用户确认模型失配声明。

#### 本批用户确认门

- 待用户分别确认 BL-04、BL-09、BL-39、BL-40、BL-47、BL-48 的证据是否回答原问题。
- 建议确认口径：
  - BL-04：接受“Viknes V1 参考 ODD / FCB45 目标 ODD”分离；FCB45 参数保留外部确认。
  - BL-09：接受“风险资格 / 物理硬门 / Evaluator profile 评分”三层分离；具体数值门后续裁决。
  - BL-39：接受当前 `head_on` tuple 为唯一 canonical 候选；Rule 13/15 场景先修复。
  - BL-40、BL-47：接受 Viknes/FLSC 仅为 synthetic reference plant，不宣称真实船校准。
  - BL-48：接受 FCB45 后续单独 target-plant qualification；Viknes 结果不得外推。
- 未确认前不改盲区为“已闭环”，不进入 Step4。

### Step3 · 第二批证据用户确认 [2026-07-28]

- 用户全部确认本批证据。
- BL-04 边界闭环：V1 ODD 为 Viknes synthetic reference ODD；FCB45 为独立 target ODD，其速度、水深和操纵包线继续标记 `EXTERNAL_CONFIRMATION_REQUIRED`。
- BL-09 闭环：风险资格、物理安全硬门和版本化 Evaluator profile 评分必须分离；具体数值门在 DP-20..25 的对应盲区中裁决。
- BL-39 闭环：当前 `head_on` 的 Viknes/FLSC、`7 m/s`、`dt=0.5 s`、无扰动 tuple 是唯一 canonical 候选；Rule 13/15 标准场景需先修复速度包线和分类。
- BL-40 边界闭环：synthetic reference plant 按用途、确定性回归、步长收敛和物理限制验收；FCB45 实船转移误差门仍需目标船数据。
- BL-47 闭环：当前 Viknes/FLSC 足够作为 synthetic canonical plant，不得宣称真实 Viknes/Telemetron digital twin。
- BL-48 边界闭环：Viknes 资格结果不得外推至 FCB45；FCB45 后续建立独立 target-plant qualification。
- Step3 尚未完成；不进入 Step4，等待用户授权下一证据批次。

### Step3 · 第三批用户授权 [2026-07-28]

- 用户确认继续调研最小闭环仿真的时序和模型失配真实性。
- 本批范围：BL-42、BL-43、BL-46、BL-49、BL-50。
- 目标：明确预测轨迹与实际执行误差、Sensor 相位语义、非整数多率调度、模型失配 profile 和规划/控制失败归因。
- 证据展示并获确认前，不标记相关 BL 闭环，不进入 Step4。

### Step3 · 闭环时序、预测误差与失败归因证据批次 [2026-07-28]

#### BL-42 · 预测轨迹与闭环实际轨迹执行误差

- [R29] 当前单步顺序为：冻结同一时刻 truth → Sensor/Tracker → Planner → 记录 state/reference/PlannerTrace → Controller 计算输入并积分 → `t += dt`。记录的 state 是区间起点状态；reference 是本区间新指令；除首步特殊计算外，`input` 却是上一积分区间留下的输入。
- `events.jsonl` 在真实求解时保存完整 horizon 和求解时刻；`trajectory.parquet` 保存每步实际 state/reference，但为节省体积删除完整 horizon。两者可通过 `solve_id` 合并，现有字段仍缺少明确的 `state_time`、`command_valid_from/to`、`applied_control_valid_from/to`。
- [R32] 当前 SB-MPC `9x60` 轨迹是简化 predictor 输出，不是 Viknes plant rollout：
  - predictor 船体固定为 `10 x 3 m`，执行 plant 为 `8.45 x 2.71 m`。
  - predictor 在未来首步后立即采用目标航向/航速，`v=r=0`；执行端是 FLSC + 3DOF Viknes，有力、速度和艏摇速率饱和。
  - horizon `150 s`、步长 `2.5 s`；求解周期 `5 s`。hold 步保留同一轨迹，但 PlannerTrace 的 `sim_time` 被改写为当前仿真步，不能把 hold 帧当新预测起点。
- [R33] 多步预测误差适合 MPC 性能监测；但接受阈值必须与模型用途分开裁决。证据支持以下计算语义：
  - 每个真实 solve 以事件中的 `solve_time` 为唯一 horizon 原点。
  - 实际状态插值到 `solve_time + k*horizon_dt`。
  - 仅评价到下一次 solve 前的“实际执行前缀”；下一 solve 之后的旧 horizon 只作 open-loop 诊断。
  - 分别输出位置误差 `e_pos`、wrap 后航向误差 `e_course`、速度误差 `e_speed` 的 one-step、RMSE、P95、max。
  - “预测模型误差”和“Controller 对 reference 的跟踪误差”分开，不能合成一个 tracking error。
- 证据边界：计算方法可闭环；当前 SB-MPC 轨迹应标记 `reference_rollout` 或 `simplified_prediction`，不能作为完整 plant-state prediction。具体通过阈值仍依赖 canonical regression/target plant 数据。
- 状态：证据已登记，未标闭环，等待用户确认上述时间对齐和指标分层。

#### BL-43 · Sensor 空扫描与“本步未扫描”的相位表示

- [R30] Radar 当前用 NaN 同时表示：未到扫描周期、目标超距、漏检。接口无法区分原因。Simulator 又只保留最近一次有限量测，导致持久化/Web 将旧量测显示成当前量测，且无量测时间戳和 age。
- `head_on` 的基础相位为：`t=0` 无 Radar scan；`1 Hz` Radar 在 `t=1.0, 2.0, ...` 扫描；KF 每个 `0.5 s` 仿真步都预测，扫描步才更新。Planner 读取本步 Tracker 输出，符合已确认的“同周期最新 Track”。
- KF 存在真值初始化泄漏：目标进入 `max_range` 后，即使本步没有有限量测，也用 `true_do_states` 初始化 Track mean。隔离实测在首个无量测时刻直接输出真值 Track。
- [R31] VIMMJIPDA Adapter 只有存在有效量测时才调用底层 step；真实空扫描不会执行 missed-detection 更新。这进一步证明空扫描语义不能继续用 `[]/NaN` 隐式表达。
- 证据支持三态扫描契约：
  - `executed=false`：本步未到 Sensor 周期；Tracker 只按自身时序预测。
  - `executed=true, detections=[]`：已扫描但无检测；Tracker 必须执行漏检更新。
  - `executed=true, detections=[...]`：扫描并检测；Tracker 预测后更新。
- 每次 scan 还需 `sensor_id/scan_id/scheduled_time/capture_time/detections`；每个 Track 需 `state_time/last_detection_time/age`。KF 正式链不得用 truth 初始化；God Tracker 保留独立真值基线。
- 状态：证据已登记，未标闭环，等待用户确认三态扫描契约和 KF 真值泄漏判定。

#### BL-46 · 非整数频率比和浮点调度容差

- [R30] 当前 Simulator 没有统一 scheduler。Sensor 和 SB-MPC 分别使用 `t-last >= period` 浮点判断，并把 `last=t`；RunSpec 接受任意正 `dt`。
- 隔离调度实测：
  - `dt=0.5 s`：`1 Hz` Radar 正常在整数秒扫描；SB-MPC 在 `5,10,15... s` 求解。
  - `dt=0.3 s`：Radar 实际变成 `1.2 s` 周期；SB-MPC 为 `5.1 s` 周期。
  - `dt=0.7 s`：Radar 实际变成 `1.4 s` 周期；SB-MPC 为 `5.6 s` 周期。
- 因 `last=t`，误差按每周期累积，不只是一次向最近 tick 量化。Gym action 路径虽拒绝非整数倍，但正式 Experiment/Session 路径无同类检查。
- 当前 V1 tuple 的 `dt_sim=0.5 s`、Radar `1 s`、SB-MPC `5 s` 均为整数比，可避免扩大 scheduler 范围。
- 证据边界：V1 最小正确方案可限定所有周期为 `dt_sim` 整数倍，并在 RunSpec 创建时拒绝不兼容组合；后续若需要非整数比，改为整数/rational tick 和绝对 `next_due`，不得继续用相对浮点累计。
- 状态：证据已登记，未标闭环，等待用户确认 V1 拒绝非整数频率比。

#### BL-49 · 模型失配 profile 的参数扰动范围和通过阈值

- [R34] 当前没有版本化 mismatch profile。RunSpec 无 plant/mismatch 字段；`model.viknes` YAML 内容被忽略，始终构造默认 `ViknesParams`，无法通过正式配置可追溯地扰动质量、阻尼、力限制或 Controller 增益。
- [R32] 当前 nominal 闭环已含结构失配：SB-MPC 简化 predictor 与 Viknes/FLSC plant 不同。因此应先按 BL-42 量化这条已存在的 nominal prediction/execution gap。
- [R27][R33] 没有目标船参数不确定度、辨识协方差或试航数据时，无法从权威资料推出通用 `±10%/±20%` 扰动和通过阈值；自行填写只能算 sensitivity study，不能算资格认证。
- 证据边界：
  - V1 `nominal_reference` profile：冻结当前 Viknes/FLSC，不增加任意参数扰动。
  - 后续 `sensitivity` profile：允许项目明确声明的探索性扰动，但结果不得标 G3/G4 robustness qualification。
  - `target_qualification` profile：必须由 FCB45 参数来源、不确定度和接受标准驱动，当前为 `UNKNOWN/EXTERNAL_CONFIRMATION_REQUIRED`。
- 状态：精确扰动范围仍为 `UNKNOWN`；证据边界已登记，等待用户确认不伪造百分比。

#### BL-50 · Controller 跟踪失败与 MPC 规划失败归因

- [R29][R34] 当前证据不足以归因：
  - Planner 异常可带 `PlanStatus`；Controller/plant/ENC 等其他异常统一落为 `NUMERICAL_FAILURE`。
  - 无 `failure_component/failure_phase`。
  - plant saturation 静默发生；未记录饱和前输入、饱和标志或约束裕度。
  - trajectory 行中的 state/reference/applied input 时间相位不一致。
  - Evaluator 只看实际轨迹，不判断预测 horizon 当时是否已不安全。
- 证据支持先建立可判定分类，而非只按最终碰撞猜原因：
  - `PLANNER_FAILURE`：无有效计划、计划本身违反同一 safety oracle、命令违反声明的 plant envelope，或 solver 状态失败。
  - `EXECUTION_FAILURE`：计划和命令在声明 envelope 内安全，但实际轨迹偏离执行前缀并超过已批准 tracking envelope。
  - `MODEL_MISMATCH_SENSITIVITY`：nominal reference plant 通过，同 episode 的声明 mismatch profile 失败。
  - `SCENARIO_OR_ORACLE_INVALID`：风险基线、地图、规则分类或 oracle 自身不满足资格前提。
  - `UNATTRIBUTED`：关键 horizon、控制相位、饱和或 target prediction 缺失；禁止强行归因。
- 归因所需最小证据：solve-time horizon、同 oracle 的预测安全裕度、command feasibility、实际 applied control、saturation、reference tracking、实际 safety outcome。Planner 与 Controller 共责时允许多标签，不采用单一“根因”覆盖证据冲突。
- 证据边界：分类语义可闭环；tracking envelope 数值依赖 BL-42/target plant，仍需后续裁决。
- 状态：证据已登记，未标闭环，等待用户确认多标签归因和 `UNATTRIBUTED` 政策。

#### 本批用户确认门

- 待用户确认 BL-42、BL-43、BL-46、BL-49、BL-50 的证据是否回答原问题。
- 建议确认口径：
  - BL-42：以真实 solve_time 对齐，只评价执行前缀；预测误差与 Controller tracking error 分开。
  - BL-43：采用三态 `MeasurementScan`；KF 真值初始化属于缺陷。
  - BL-46：V1 只允许 `dt_sim` 整数倍周期；非整数多率后置。
  - BL-49：V1 不伪造参数扰动；FCB45 robustness range 保留外部确认。
  - BL-50：采用证据驱动多标签归因；证据不足必须 `UNATTRIBUTED`。
- 未确认前不改盲区为“已闭环”，不进入 Step4。

### Step3 · 第三批证据用户确认 [2026-07-28]

- 用户全部确认本批证据。
- BL-42 闭环：以真实 solve-time 对齐，只评价下一 solve 前的执行前缀；prediction error 与 Controller reference tracking error 分开统计。
- BL-43 闭环：扫描采用 `executed=false`、空扫描、有效检测三态契约；当前 KF 无有效量测时的 truth 初始化属于缺陷。
- BL-46 闭环：V1 所有 Sensor/Planner 周期必须为 `dt_sim` 整数倍，不实现通用非整数多率 scheduler。
- BL-49 边界闭环：V1 仅冻结 `nominal_reference` plant，不伪造参数扰动百分比；FCB45 robustness range 继续标记 `EXTERNAL_CONFIRMATION_REQUIRED`。
- BL-50 闭环：采用 `PLANNER_FAILURE`、`EXECUTION_FAILURE`、`MODEL_MISMATCH_SENSITIVITY`、`SCENARIO_OR_ORACLE_INVALID`、`UNATTRIBUTED` 多标签归因；关键证据缺失时禁止推测根因。
- Step3 尚未完成；不进入 Step4，等待用户授权下一证据批次。

### Step3 · 第四批用户授权 [2026-07-28]

- 用户确认继续调研 ENC、碰撞/搁浅和任务终止真实性。
- 本批范围：BL-51、BL-52、BL-53、BL-54、BL-55。
- 目标：明确可用海图安全层、船体/扫掠安全 oracle、goal reached 语义，以及后置风流 profile 的证据边界。
- 证据展示并获确认前，不标记相关 BL 闭环，不进入 Step4。

### Step3 · ENC、碰撞/搁浅和任务终止真实性证据批次 [2026-07-28]

#### BL-51 · ENC 水深、安全等深线、吃水和潮汐

- [R35] 当前 `More_og_Romsdal_utm33.gdb` 不是“没有水深”：
  - 原始 GDB 含 `dybdeareal`、`dybdekurve`、`dybdepunkt`、`datakvalitet` 等 layer；`dybdeareal` 有 `minimumsdybde/maksimumsdybde`，`datakvalitet` 有 `catzoc`。
  - `head_on` 的 `25 km²` 窗口实测含 `0.5/2/3/5/6/10/15/20/30/40/50/100/200 m` 深度区和 `A1/A2/B` 三类 CATZOC。
  - SeaCharts runtime 只加载 `seabed/land/shore`，按 `[0,1,2,5,10,20,50,100,200,350,500] m` 重分箱；不暴露 `datakvalitet/CATZOC`。Viknes `draft=0.5 m` 被向上选择到 `1 m` runtime layer；本窗口 `1 m` 与 `2 m` geometry 实测相同。
- 当前 hazard 定义为 `land ∪ shore ∪ (seabed[0] - seabed[min_depth])`。Simulator 只按 ownship draft 构造一次 hazards，之后也用于所有目标船；不同吃水目标船会得到错误 grounding 语义。live grounding 不把越出 ENC bbox 自动判为失败。
- [R36] IHO S-57 将 DEPARE 定义为 `DRVAL1..DRVAL2` 深度范围，不是连续高分辨率海床；M_QUAL/CATZOC 单独表达资料质量。Kartverket 明确不同测量年代和方法造成质量差异，B/C/D/U 区域可能存在未发现或偏差较大的水深。
- [R37] IMO A.893(21) 要求同时考虑船舶允许吃水、可用水深、最小 UKC、转向引起的 squat/heel、潮高/潮流、定位准确性和操纵特性。当前代码只做“静态吃水向上匹配离散深度层”，不含 UKC、潮汐、squat、heel、CATZOC 或定位误差。
- 证据边界：
  - 当前数据足够定义可复现的 `chart_geometric_clearance` synthetic V1 oracle：在 ENC bbox 内，船体不进入按该船吃水选出的 runtime hazard。
  - 它不等于 operational UKC，也不得宣称真实航行安全。目标船/目标海域资格需另给 UKC、潮汐、squat/heel、CATZOC/测量误差 profile。
  - 每艘船必须独立派生 `required_depth` 和 hazards；不能复用 ownship hazards。
- 状态：证据已登记，未标闭环，等待用户确认上述 synthetic V1 声明边界。

#### BL-52 · Grounding footprint、扫掠几何和时间离散容差

- [R38] 当前 live grounding 是“船舶中心点到 hazard 的距离 `<= length/2`”；不使用航向、宽度、模型 `ship_vertices` 或现有 `create_ship_polygon()`。这既可能漏报舷侧/船艏接触，也可能把中心仍距岸较远的安全姿态误报。
- 当前只检查积分后的离散姿态，没有区间扫掠。canonical `7 m/s`、`dt=0.5 s` 每步平移约 `3.5 m`，再叠加转动产生的角点位移；由此可推断窄 hazard 或步间穿透可能被端点采样漏掉。
- `extract_relevant_grounding_hazards_as_union()` 会删除 Polygon interior，可能把原本的 geometry hole 填成 hazard；需以地图 golden geometry 测试确认是否为有意保守化。
- 重建 Evaluator 的 grounding 当前不可用：`VesselData.compute_closest_grounding_dist()` 调用不存在的 `map_functions.compute_closest_grounding_dist()`；Evaluator 又用宽泛 `except Exception` 将结果静默改成 `None`。因此现有 `grounding_count=0` 不能作为“无搁浅”证据。
- 证据支持的 oracle 结构：
  - 每状态：使用该船模型 footprint/明确 fallback footprint，与该船 hazards 和 ENC bbox 做相交/包含检查。
  - 每区间：在 `t_k -> t_{k+1}` 对位置和最短角差做连续扫掠或可证明上界的自适应姿态细分。
  - `physical grounding` 与额外安全 buffer 分开；buffer 不改变“是否实际接触”的事实定义。
- 证据边界：需要 sweep，结论可闭环；最大角点位移、几何精度和接受误差的具体数值仍属 BL-65/66，当前为 `UNKNOWN`，不得随意填固定厘米/米数。
- 状态：证据已登记，未标闭环，等待用户确认 footprint+sweep 结构及数值容差后置。

#### BL-53 · Collision 的事实判定与 CPA/安全域

- [R25][R38] 当前存在两个互不一致的 collision predicate：
  - Simulator：中心距 `<= ownship.length/2`；忽略目标船尺寸、宽度和姿态。
  - Evaluator：中心距 `<= (ownship.length + target.length)/2`；仍忽略宽度、姿态和步间扫掠。
- 对两个 Viknes，阈值分别为 `4.225 m` 和 `8.45 m`。因此同一 `head_on` Nominal 最小中心距约 `7.43 m` 时，Simulator 可判无碰撞、Evaluator 判碰撞。事实事件不能依赖调用入口。
- `compute_distance_vectors_to_dynamic_obstacles()` 虽接收目标船 length/width，计算时仍只使用中心点匀速距离；CPA/中心距适合作风险诊断，不足以定义物理碰撞。
- 证据支持单一权威 oracle：
  - `physical_collision`：truth 下两船定向 footprint 在离散端点或区间扫掠中相交/接触。
  - `clearance_m`：两 footprint 间最小几何距离，接触后为 `0`。
  - `safety_domain_violation`、CPA/TCPA、near-miss：独立版本化风险指标，不得改写 `physical_collision`。
  - Simulator、Session、Gym、Evaluator 共用同一实现和事件时间语义。
- 证据边界：事实/风险分离可闭环；footprint fallback、插值和数值容差继续由 BL-65/66 裁决。
- 状态：证据已登记，未标闭环，等待用户确认禁止 CPA/中心距充当物理碰撞事实。

#### BL-54 · Goal reached 的位置、航向、速度和保持时间

- [R38] 当前 `determine_ship_goal_reached()` 只检查位置：
  - 默认半径为 `7 x length`：Viknes `59.15 m`，FCB45 将达 `315 m`。
  - 不检查航向、速度、路径进度或保持时间。
  - waypoint 分支对任意 `ship_idx` 都错误读取 `self.ownship.waypoints`。
- `head_on` 使用两点、`7 m/s` 的巡航路线；LOS 的 route switching 使用 pass-angle 或 `R_a=15 m`，而终止半径为 `59.15 m`。当前 run 可能在 guidance 抵达最终 waypoint 语义之前提前完成。
- 同一 predicate 无法同时表达两类任务：
  - `route_exit`：标准动态避碰 episode。船舶穿过终端 gate/达到最终沿程进度，并满足横向 corridor、终端航向和正向进度；不要求停船，也不要求在终点圆内保持。
  - `terminal_state`：明确提供最终位置/航向/速度的靠泊或状态任务。四项进入容差，并保持声明时长。
- [R29][R38] Session 还存在终止时间相位错位：snapshot 的 `sim_time/payload state` 是积分前时刻，goal predicate 却读取积分后状态，事件默认时间为积分后时刻。结束证据必须绑定 post-step state，或记录区间内首次 crossing 时间，不能挂在 pre-step frame 上。
- 证据边界：当前标准 HO/crossing/overtaking 应使用 `route_exit`；精确 gate/corridor/航向容差由 BL-75 裁决。未来 `goal_csog_state` 才使用 `terminal_state`，其位置/航向/速度/hold 数值目前为 `UNKNOWN`。
- 状态：证据已登记，未标闭环，等待用户确认双模式语义和 V1 `route_exit`。

#### BL-55 · 后续风流扰动 profile 的参数来源和范围

- [R39] 当前仓库存在 Gauss-Markov 风流实现和若干场景参数，但没有参数来源/校准证据：
  - RL 场景示例为 current `0..1.5 m/s`、wind `0..5 m/s`；Boknafjorden 示例为二者 `0..1 m/s`。
  - 上游 PSB corpus 生成器人为设定 wind `0..6 m/s`、current `0..3 m/s`，方向均匀采样；这些是 benchmark 构造参数，不是目标海域/船型 metocean qualification range。
  - PSB 派生 disturbance episode 同时修改 LOS/FLSC 参数和目标船 plant，故 nominal/constant/variable 不是纯粹只改变环境的因果对照。
- 当前实现还存在资格边界：
  - `GaussMarkovDisturbance.__init__()` 强制关闭 `add_impulse_noise`，配置的 impulse 实际不执行。
  - 缺失 initial value/impulse time 时使用未注入的全局 `random` 或新 RNG；wind/current reset 又使用同一 seed 创建相同随机序列，独立性未建立。
  - Viknes 风载面积/系数被源码标为 crude guessed values；current 是均匀、无旋假设；waves 未实现。
- [R37] IMO 证据支持“潮流、水流、气象必须纳入真实航行规划”，但不提供任何可直接复制到当前船型/海域的数值范围。
- 证据支持两类后置 profile，不能混名：
  - `source_reproduction`：冻结 PSB episode 的原始风流参数，用于上游算法/论文 corpus 重放；保留其同时更改 controller/plant 的 provenance。
  - `target_sensitivity/qualification`：只有取得目标海域 metocean 数据、FCB45 风流模型和不确定度后才能建立。当前精确范围为 `EXTERNAL_CONFIRMATION_REQUIRED`。
- 状态：证据边界已登记，未标闭环，等待用户确认 V1 继续无扰动，PSB profile 只作 source reproduction，不伪装 target robustness。

#### 本批用户确认门

- 待用户确认 BL-51、BL-52、BL-53、BL-54、BL-55 的证据是否回答原问题。
- 建议确认口径：
  - BL-51：V1 只声明 `chart_geometric_clearance`；每船独立按静态吃水派生 hazards；不宣称 operational UKC。
  - BL-52：grounding 使用 vessel footprint + interval sweep；具体数值容差后置 BL-65/66。
  - BL-53：physical collision 只由 truth footprint/sweep 定义；CPA、中心距和安全域保持独立。
  - BL-54：标准动态场景采用 `route_exit`；`terminal_state` 仅用于显式终端状态任务；修复 post-step 事件时间。
  - BL-55：V1 无扰动；PSB 扰动只作 source reproduction；目标 robustness 范围等待外部数据。
- 未确认前不改盲区为“已闭环”，不进入 Step4。

### Step3 · 第四批证据用户确认 [2026-07-28]

- 用户确认本批全部证据。
- BL-51 边界闭环：V1 仅声明逐船 `chart_geometric_clearance`，按静态吃水独立派生 hazards；UKC、潮汐、squat/heel、CATZOC 不确定度继续标记 `EXTERNAL_CONFIRMATION_REQUIRED`。
- BL-52 边界闭环：grounding 使用 vessel footprint + interval sweep；footprint fallback、插值和数值容差继续由 BL-65/66 裁决。
- BL-53 闭环：`physical_collision` 只由 truth footprint/sweep 定义；CPA、中心距、安全域和 near-miss 保持独立风险指标；所有运行入口共用同一 oracle。
- BL-54 边界闭环：标准动态场景采用 `route_exit`，显式终端状态任务采用 `terminal_state`；具体 gate/corridor/航向/速度/hold 阈值转 BL-75，并修复 post-step 事件时间语义。
- BL-55 边界闭环：V1 保持无扰动；PSB 风流只作 `source_reproduction`；目标海域/FCB45 robustness range 继续标记 `EXTERNAL_CONFIRMATION_REQUIRED`。
- Step3 尚未完成；不进入 Step4，等待用户授权下一证据批次。

### Step3 · 第五批用户授权 [2026-07-28]

- 用户确认继续调研确定性重放和跨运行环境证据边界。
- 本批范围：BL-56、BL-57、BL-58、BL-59、BL-60。
- 目标：明确 exact/tolerance replay 分层、PSB/RLMPC 非确定性来源、当前 RNG 缺口、路径相关 Sensor 公平性，以及 runtime fingerprint。
- 证据展示并获确认前，不标记相关 BL 闭环，不进入 Step4。

### Step3 · 第五批深度调研：确定性、公平随机流与运行时身份 [2026-07-28]

#### BL-56 · exact 与 tolerance replay 的边界

- [R40] 当前 replay 只有一种判定：重新构造 `RunSpec`，要求 `episode_hash` 相等，并比较整个 `trajectory.parquet` 文件 SHA-256。`reproduction_level` 不改变 replay 行为。
- 当前文件 hash 混合了两件事：
  - 仿真数值是否相同。
  - Pandas/PyArrow 产生的 Parquet 二进制编码和 metadata 是否相同。
  后者变化不能自动证明算法轨迹变化；只比较文件 hash 又不能指出哪个状态、指令、计划或规则判定漂移。
- [R42] NumPy 明确说明：固定 seed 不能保证跨 NumPy version、OS、CPU、build 或 LAPACK 的完整 bit-exact；`multivariate_normal()` 尤其可能因 LAPACK 改变。exact 必须绑定运行时，而非只绑定 seed。
- 证据支持将“证据播放”和“重新执行验证”分开：
  - `artifact playback`：Web 只读既有六件证据包，不重新运行算法；校验 artifact/schema/content hash。
  - `exact rerun`：仅在 runtime fingerprint 相同、Adapter 声明并通过 exact repeatability probe 时启用。episode、调度、requested/executed identity、状态、事件顺序和规范化数值内容必须 exact；不以 Parquet 文件字节作为唯一数值 oracle。
  - `tolerance rerun`：用于 native solver 或经批准的跨 runtime 重放。离散语义仍 exact，包括 solve/hold 序列、算法/Tracker 身份、失败状态、碰撞/搁浅/COLREG 硬判定；连续数组按字段化 `atol/rtol` 比较。wall-clock/solve time 不参与数值相等，只作性能诊断。
- tolerance 不是“结果大致相同”：任何硬安全/COLREG verdict、选择分支、solver status 或失败标签变化，均判 replay 失败。
- 证据边界：当前可确定双模式和比较对象；每个 native Adapter 的数值 `atol/rtol` 必须来自重复试验和数值尺度，不能在此填统一常数。
- 状态：证据已登记，未标闭环，等待用户确认 exact/tolerance 双模式。

#### BL-57 · PSB-MPC/RLMPC 的已知非确定性与容差

- [R43] PSB-MPC 的公开配置使用 CE collision probability estimation，`n_CE=500`；公开 pybind 接口暴露 `CPE.set_seed()`。当前 Adapter 新建 CPE 后未设置 seed，Runner 又只向 RRT 注入 `algorithm` seed。因此当前 PSB 输出不具备受控随机重放条件。
- PSB 的数值 core 位于当前未公开/未检出的 `external/thecolavrepo` submodule。公开 CMake 使用 C++20、Eigen、Boost、`-flto=auto`，但不能据此证明 core 是否使用并行 reduction、固定 RNG engine 或稳定迭代顺序。上游 benchmark 的 multiprocessing 是 episode 级并行，不等于单次 solve 内并行。
- [R44] 当前 RLMPC registry 直接构造 `rlmpc_cas.RLMPC`，不是 learned Torch policy。标准配置使用生成的 Acados solver、SQP、partial-condensing HPIPM、exact Hessian、warm start 和明确 solver tolerance；正常 `plan` 路径未发现启用随机 NLP perturbation。
- RLMPC 的 warm start、native generated code、solver/build/version和浮点线性代数仍构成跨 runtime 漂移边界。上游 RL evaluation 将 action 设为 deterministic，常用 CPU；这不等于当前 native solve 跨平台 bit-exact。
- [R45] 若后续启用 learned parameter provider，PyTorch 官方明确不保证跨 release、platform 或 CPU/GPU 的完整复现；该 runtime/device 必须纳入身份，且默认进入 tolerance rerun。
- 证据支持最小准入政策：
  - PSB：先接入 `algorithm_seed -> CPE.set_seed()`，隔离 Worker，记录 native binary/build；未取得私有 core 和重复性证据前为 `tolerance-only`。
  - RLMPC：记录 Acados/HPIPM/CasADi/config/codegen binary identity；跨 runtime 为 `tolerance-only`。同 runtime 只有在 cold reset、warm reset 和 Worker 重建重复性 probe 均零漂移后，才能声明 exact。
  - batch 可并行 run，但每 run 独立 Worker、独立 seed tree；并发数和线程环境进入 runtime profile。
  - Adapter 单独冻结字段化 tolerance profile；硬 verdict 永不放宽。
- 状态：证据已登记，未标闭环，等待用户确认 native 默认 tolerance-only，exact 必须实测晋级。

#### BL-58 · 当前 RNG 缺口与最小 seed tree

- [R40][R41] `SeedBundle` 已由根 seed 派生 `scenario/sensor/tracker/algorithm` 四个 child seed，但当前接线不完整：
  - `scenario` seed 已进入 `ScenarioGenerator`，RRT behavior 使用同一 scenario seed。
  - `sensor` seed 被传给 `SimulationSession`，随后同一个 seed 重置所有船、所有 Radar/AIS，以及 wind/current。
  - `tracker` seed 未被 Runner 或 Tracker 使用。
  - `algorithm` seed 仅传给 RRT；VO、SB-MPC、PSB、RLMPC、Custom Adapter 无统一 seed 生命周期。
- `core/stochasticity.py` 仍存在未注入随机源：缺失 initial speed/direction 时调用 Python global `random.uniform()`；缺失 impulse time 时新建无 seed `default_rng()`。
- 每个 Sensor 虽有私有 Generator，但所有船/所有 Sensor 用相同 seed，产生相同起始随机序列；wind/current 也用同 seed，形成不应有的相关性。
- [R42] NumPy 推荐通过 `SeedSequence.spawn()` 或根 seed + 唯一稳定 ID 派生独立流。仅按可变列表顺序连续 `spawn` 会让新增组件改变旧组件 seed，故证据包需要稳定组件路径。
- 证据支持最小 `SeedTree`：
  - 根：`run_seed`。
  - 稳定路径：`scenario`、`sensor/{ship_id}/{sensor_id}`、`tracker/{ship_id}`、`disturbance/{wind|current}`、`algorithm/{ship_id}/{algorithm_id}`。
  - 路径与 RNG scheme/version 写入 manifest；组件只持有自己的 Generator，不调用 global RNG。
  - Adapter 契约增加 seed/reset 输入；PSB 等 native RNG 显式映射；无 seed API 的 native dependency 不获得 exact 资格。
- 状态：证据已登记，未标闭环，等待用户确认以稳定组件路径取代共享 seed。

#### BL-59 · 路径相关 Sensor 可见性下的算法公平性

- [R41] 当前 Radar/AIS 的可见性由每个 run 的 ownship 位置和 `max_range` 决定。不同算法改变 ownship 轨迹后，可见目标和量测时刻自然可能不同；强行给所有算法相同“已实现量测”会向某些轨迹注入物理上不可见的数据。
- 当前顺序 RNG 又制造了额外不公平：
  - Radar 对目标先抽 detection uniform；仅检测成功再抽噪声；最后按 scan 抽 clutter。
  - AIS 仅在到期且目标在范围内时抽噪声。
  一条路径改变一次可见/检测分支，会改变后续 RNG 消耗位置；之后即使两算法再次处于相同几何，也不再共享相同随机冲击。
- [R46] Common Random Numbers 的正确用途是让被比较系统共享同一外生随机输入、提高配对差值精度；不是要求系统状态变化后仍获得同一观测结果。
- 证据支持公平定义：
  - 冻结相同 episode、目标 truth、ENC、plant/controller、Sensor/Tracker 参数和 Evaluator。
  - 用稳定 key `(sensor_seed, sensor_id, scan_id, target_id, draw_kind)` 生成 detection/noise；clutter 用 `(scan_id, clutter_index)`。算法路径不改变后续随机 key。
  - 每个 run 仍用自己的 truth ownship 几何判断 range/visibility；不可见则不产生量测。
  - 同时记录 `in_range/exposed/detected/scan_count`，解释闭环感知差异。
  - God profile 用于纯算法确定性能力比较；KF profile 是独立的闭环感知鲁棒性比较。二者不混成一张能力结论。
- 该 keyed CRN 可实现为确定性 `SensorNoiseTape`/无状态 keyed draw，不需要预生成完整传感器世界，也不复制第二仿真引擎。
- 证据边界：公平语义可闭环；G4 配对统计方法和 KF exposure 分层仍归 BL-88。
- 状态：证据已登记，未标闭环，等待用户确认“路径相关可见性合法，随机冲击按稳定 key 配对”。

#### BL-60 · runtime fingerprint 是否进入 replay identity

- [R40] 当前 Manifest 仅记录短 Python version、`platform.platform()`、项目 commit/dirty 和外部模块的 available/version/source/repo commit。它未记录 CPU/architecture、Python compiler/build、BLAS/LAPACK/SIMD、native binary hash、compiler/build flags、solver codegen、线程环境或 GPU runtime。
- [R42] NumPy 指出 OS、CPU、build 和 LAPACK 可改变 RNG/数值结果；[R45] PyTorch 对 release/platform/device 有同类边界。[R47] `numpy.show_runtime()` 可报告 BLAS/LAPACK、threadpool 和 SIMD；SLSA provenance 将 builder、build definition、parameters 和 materials 作为可追溯 build 身份。
- 证据支持 `runtime_fingerprint` 最小字段：
  - OS/kernel、machine architecture、CPU model。
  - Python implementation/version/build/compiler。
  - lockfile hash及关键 Python package version。
  - NumPy/SciPy numeric runtime：BLAS/LAPACK、SIMD、threadpool。
  - native Adapter：repo SHA、module/binary SHA、solver/library version、compiler/CMake/build flags、codegen/config hash。
  - thread/concurrency 环境；仅实际使用 GPU 时记录 device、driver、CUDA/cuDNN。
- 判定政策：
  - exact rerun 要求 fingerprint 相同。
  - tolerance rerun 允许声明过的 fingerprint 差异，但必须把 diff 写入 replay result。
  - solve time/性能排名要求相同的 performance profile；wall-clock 不属于轨迹 exact hash。
- 状态：证据已登记，未标闭环，等待用户确认 runtime fingerprint 为 replay identity，而非普通备注。

#### 本批用户确认门

- 待用户确认 BL-56、BL-57、BL-58、BL-59、BL-60 的证据是否回答原问题。
- 建议确认口径：
  - BL-56：区分 artifact playback、exact rerun、tolerance rerun；tolerance 不放宽离散身份和硬 verdict。
  - BL-57：PSB/RLMPC native 默认 `tolerance-only`；仅经同 runtime 重复性 probe 才晋级 exact。
  - BL-58：建立稳定组件路径 SeedTree；清除 global/unseeded/shared RNG。
  - BL-59：路径相关 visibility 属真实闭环差异；用 keyed CRN 消除调用顺序造成的伪差异；God/KF 分 profile。
  - BL-60：runtime fingerprint 进入 replay identity；exact 要求相同，tolerance 保留并报告差异。
- 未确认前不改盲区为“已闭环”，不进入 Step4。

### Step3 · 第五批证据用户确认 [2026-07-28]

- 用户确认第五批全部证据。
- BL-56 闭环：证据播放、exact rerun、tolerance rerun 分离；tolerance 不放宽离散身份、solver status 和硬安全/COLREG verdict。
- BL-57 边界闭环：PSB/RLMPC native 默认 `tolerance-only`；只有同 runtime 重复性 probe 零漂移后才能晋级 exact。
- BL-58 闭环：采用稳定组件路径 SeedTree；禁止 global、unseeded 和跨组件共享 RNG。
- BL-59 闭环：ownship 路径相关 visibility 属真实闭环差异；使用 keyed CRN 消除调用顺序伪差异；God/KF 分 profile。
- BL-60 闭环：runtime fingerprint 进入 replay identity；exact 要求相同，tolerance 必须记录 fingerprint diff。
- Step3 尚未完成；不进入 Step4。

### Step3 · 第六批用户授权 [2026-07-28]

- 用户要求执行下一批调研。
- 本批范围：BL-61、BL-62、BL-63、BL-64。
- 目标：明确独立 Evaluator 的硬门/评分/诊断边界、当前重建实现与论文差异、多硬门聚合状态，以及 multi-ship pairwise 冲突和场景级聚合。
- 证据展示并获确认前，不标记相关 BL 闭环，不进入 Step4。

### Step3 · 第六批深度调研：独立资格门、论文 Evaluator 差异与多船聚合 [2026-07-28]

#### BL-61 · 硬门、评分和诊断的边界

- [R2] 论文 Evaluator 的原生输出是 `0..1` score/penalty。论文没有定义统一“通过分数”，且明确参数和权重依赖研究者对模糊 COLREG 术语的解释。把 `S14 >= x` 直接当法规硬门，将新增一个论文未给出的资格政策。
- [R50] 2024 扩展同样保持该边界：grounding check 产生独立 `P_gr`，不并入 situation score；grounding hazard compensation 只调整部分 COLREG penalty。对 Playground 而言，truth grounding 仍是物理硬失败，不能因 score compensation 变成通过。
- 证据支持三层输出，禁止互相替代：

| 层 | 内容 | 资格语义 |
|---|---|---|
| 硬资格门 | 证据/身份有效；无 fallback；执行链完成；零 truth collision/grounding/map exit；全部适用的定向 COLREG 行为 predicate 通过；任务/控制/实时门通过 | 任一必需门失败即不合格；不得被分数抵消 |
| 研究评分 | 论文 profile 的 `S_safety`、`S_r`、`S_theta`、`S8`、`S13..S17` 及对应 `P_*`/compensation | 用于解释质量和同 profile 比较；不是法规事实或单独资格门 |
| 诊断 | DCPA/TCPA、footprint clearance、CPA pose、阶段/角色、机动起止、路径偏差、控制饱和、solve status/time/iterations、Tracker 误差 | 定位原因；不参与通过判定，除非另有版本化 predicate 引用 |

- COLREG 硬门不是对论文总分设任意阈值，而是另存可审计的行为事实，例如“Rule 14 角色已锁定、未向左转、满足通过侧 predicate”。具体角度、阶段、及时/明显、通过侧阈值仍由 BL-70..BL-74 裁决；未裁决前该门只能是 `NOT_EVALUATED`，不能静态宣称 G3。
- 任务、deadline 和控制可执行性阈值仍由 BL-75..BL-82 裁决。物理 oracle 的 footprint、扫掠和容差仍由 BL-65/66 裁决。当前只能冻结分层和“不以高分补偿硬失败”的语义，不能提前伪造数值门。
- 失败 run 仍保存可计算 score 和全部诊断，但只用于失败分析；效率排名只接收全部必需硬门为 `PASS` 的 run。
- 状态：证据已登记，未标闭环，等待用户确认三层边界。

#### BL-62 · 当前 reconstructed Evaluator 与论文公式的已知偏差

- [R48] 当前实现已诚实标记 `reconstructed-evaluator-v1`、`functional_reproduction` 和 `numerical_reproduction_confirmed=False`。但其差异不是小数容差，而是评价语义尚未实现：
  - **预处理**：论文先去 NaN、统一 NED/单位、固定采样间隔线性插值、Gaussian smoothing，再用有限差分检测机动；当前 Evaluator 只取两个 timestamp 的精确交集，没有在评价入口执行该流水线。
  - **遭遇切片**：论文以进入 Stage 2 为 encounter 起点、回到 Stage 1 为终点，并允许同一 pair 多次 encounter；当前从整段首个共同样本评价到结束。
  - **分类与阶段**：论文在 Stage 2 entry 按双方 pose 和版本化角度分类，采用可配置 Stage 2/3/4 距离；当前先用 `max(500 m, 10 x length_sum)` 做风险筛选，再以 `8 x/4 x length_sum` 和 post-CPA 生成 `0..3` 阶段。
  - **安全公式**：论文 `S_r` 是 `r_pref/r_min/r_nm/r_col` 四段函数，`S_theta` 来自 CPA contact angle/relative bearing，`S_safety` 再按式 (2) 合成；当前分别使用 `min_distance/(3 x length_sum)`、95 分位 course step 和 `min_distance/length_sum`。
  - **规则公式**：论文 Rule 13..17 使用 delayed action、apparent course/speed、passing side/ahead、Stage 2/3 stand-on、Stage 4 port turn及权重组合；当前以 `5/15 deg`、平均速度和 `initial TCPA` 构造简化启发式，字段同名但公式不同。
  - **方向性**：论文评价“每艘船相对每个相遇目标”；当前 `combinations(vessels, 2)` 每个无序 pair 只输出一次，并把列表中第一艘当 ownship。反向角色、反向 Rule 14 和 stand-on/give-way 责任会丢失。
  - **多船补偿**：论文只对矛盾职责提供 `C_x,gw`；当前 `C_x_gw` 实际由 crossing 场景的 port change/15 deg 生成，语义不相同。
  - **ENC**：当前 grounding 距离调用异常会被全捕获并转成 `None`，既未形成可靠物理硬门，也未实现 2024 alternative-trajectory compensation。
  - **聚合**：当前对所有 pair 的同名非空 metric 直接算均值；论文示例保留每 vessel 对每 encountered vessel 的独立结果，没有定义这个场景总均值。
  - **运行状态**：当前 BatchRunner 只要 Runner 未抛异常就写 `SUCCESS`；碰撞、搁浅、规则低分和未完成任务不改变 qualification status。连续指标只在该 `SUCCESS` 子集算均值/正态近似 CI。
- [R49] 历史接口还保留 `set_enc()`、`set_vessel_data()`、无参 `evaluate()`、逐船打印/绘图；当前只保留 `evaluate(vessels, enc)`。可在不改变新上层契约的前提下提供兼容 facade，但核心优先级必须是公式和 golden tests，不是方法名外观。
- 当前单测只证明合成 head-on 字段存在和无重叠样本会告警；未覆盖论文 Tables I/II、Ocean Engineering Tables 7/9/11、Stage 1..4、双向职责、多次 encounter 或 grounding compensation。
- 结论：当前模块可验证“证据流和字段流”，不能作为论文数值 Evaluator，也不能独立授予 G3。最小修复顺序固定为：预处理/encounter slicing -> 双向角色与阶段 -> 论文 open-water 公式/profile -> 表格 golden tests -> 硬资格门 -> 2024 grounding compensation。
- 状态：差异已登记，未标闭环，等待用户确认是否把当前实现正式降级为 `evidence-flow stub`。

#### BL-63 · 多项硬门失败的优先级与聚合状态

- 单一 `SUCCESS/FAILED` 无法表达“求解完成但碰撞”“先碰撞后 native crash”“执行失败导致 COLREG 未评价”。证据支持每个 gate 独立保存：

```text
gate.status = PASS | FAIL | NOT_EVALUATED
qualification_status = PASS | FAIL | NOT_EVALUATED | INVALID
failed_gates[] / not_evaluated_gates[] / primary_reason
```

- 场景级聚合规则：
  1. 证据 schema、truth、requested/executed identity、profile 或 fallback 证明无效：`INVALID`。
  2. 否则任一必需 gate 为 `FAIL`：总体 `FAIL`。
  3. 无失败，但任一必需 gate 为 `NOT_EVALUATED`：总体 `NOT_EVALUATED`。
  4. 仅当全部必需 gate 为 `PASS`：总体 `PASS`。
- `primary_reason` 只服务 UI 和失败路由，不删除并发失败。确定性顺序采用：`INVALID_EVIDENCE -> observed PHYSICAL_SAFETY -> EXECUTION_INTEGRITY -> COLREG_BEHAVIOR -> TASK/CONTROL/REALTIME`。例如 collision 与 Rule 14 同时失败时，主原因为 collision，但两项都保留。
- crash、dependency unavailable、timeout 无有效计划均是执行门失败；它们使后续未观察到的安全/规则门成为 `NOT_EVALUATED`，但总体仍为 `FAIL`。缺 evaluator/profile 导致无法评分且没有算法失败时为 `NOT_EVALUATED`，不得误写 `PASS`。
- 批量结果必须保留 `n_requested/n_valid/n_pass/n_fail/n_not_evaluated/n_invalid`，失败率分母不删除 crash、timeout、fallback 或缺失依赖。连续 score 单独报告 `n_evaluated`；失败 run 的诊断可展示，但不能进入通过样本的效率排名。
- 不生成能抵消硬失败的总分。不同失败类别并列统计；优先级不代表法律严重度或科学权重。
- 状态：证据已登记，未标闭环，等待用户确认四态聚合和主原因顺序。

#### BL-64 · Multi-ship pairwise 冲突与场景级聚合

- [R2] 论文明确：同一时间存在多个 encounter 时，每艘船相对每艘遇到的船独立评价。论文也明确 COLREG 没有给出矛盾职责的统一处理规则；其唯一 multi-ship 特例是 stand-on penalty 的 give-way compensation `C_x,gw`。CCTA Table II 同样逐个 `OS -> DO` 展示，不给一个场景总分。[R1]
- 因此数据模型必须区分三种粒度：
  - `physical_pair_id = sorted(vessel_a, vessel_b)`：无序物理 pair，只计一次 collision/clearance。
  - `obligation_id = ownship -> target + encounter_episode_id`：有向规则责任；同一物理 pair 通常有两个方向的评价。
  - `vessel_id/scenario_id`：任务、控制、grounding 和最终资格聚合。
- 每个物理 pair 可随“进入 Stage 2 -> 回到 Stage 1”产生多个 `encounter_episode_id`。角色在 episode entry 锁定；不能因算法转向而重分类逃离原责任。
- 同一 vessel 的多个 obligation 时间窗重叠时，记录 `simultaneous_obligation_set`、角色组合和时间范围。Evaluator 不发明“应优先哪条船”的战术策略：
  - 实际行为仍对每个适用 obligation 独立判定。
  - 矛盾职责本身不自动判失败；实际未满足的 obligation 才失败。
  - `paper_compatible` score profile 可按论文应用 `C_x,gw`；该补偿不得修改 physical safety、不得把未满足的硬 COLREG predicate 改为通过。
- 场景硬门采用保守合取：
  - 任一无序 pair collision、任一 vessel grounding/map exit：physical safety `FAIL`。
  - 任一必需有向 obligation 失败：COLREG behavior `FAIL`。
  - 任一受控 vessel 的执行/任务门失败：相应场景门 `FAIL`。
- 不把 pair score 平均值当资格。报告保留逐 obligation、逐 vessel、逐 rule 结果；可另给 per-rule macro mean、worst applicable score 和分布作为项目诊断，但必须标记 `non-paper aggregate`，不得伪装 CCTA/Ocean Engineering 原始输出。
- V1/V2 双船可先实现同一数据模型；V3 multi-ship 只增加 obligation 数量和 conflict-set 展示，不另建第二套 Evaluator。
- 状态：证据已登记，未标闭环，等待用户确认“无序物理事实 + 有向规则责任 + 场景合取”的聚合结构。

#### 本批用户确认门

- 待用户确认 BL-61、BL-62、BL-63、BL-64 的证据是否回答原问题。
- 建议确认口径：
  - BL-61：硬资格门、论文研究评分、原始诊断三层分离；score 不抵消硬失败。
  - BL-62：当前 reconstructed Evaluator 正式视为 `evidence-flow stub`；按论文公式/profile 和 golden tables 重建后才可授予 G3。
  - BL-63：gate 独立三态、qualification 四态；保留全部失败，主原因只用于展示。
  - BL-64：物理 pair 无序去重、规则 obligation 有向评价、场景硬门合取；论文 `C_x,gw` 只补偿 score。
- 未确认前不改盲区为“已闭环”，不进入 Step4，不实施代码。

### Step3 · 第六批证据用户确认 [2026-07-28]

- 用户确认第六批全部证据。
- BL-61 边界闭环：硬资格门、论文研究评分、原始诊断三层分离；score 不得抵消硬失败；物理、COLREG、任务和 G3 数值 predicate 继续由 BL-65..BL-82 裁决。
- BL-62 闭环：当前 `reconstructed-evaluator-v1` 定级为 `evidence-flow stub`；完成论文 open-water 公式、双向角色、阶段、profile 和 golden tables 前，不得用其授予 G3 或宣称论文数值复现。
- BL-63 闭环：gate 使用 `PASS/FAIL/NOT_EVALUATED`，qualification 使用 `PASS/FAIL/NOT_EVALUATED/INVALID`；全部并发失败保留，`primary_reason` 只用于展示和路由。
- BL-64 闭环：物理 pair 无序去重、规则 obligation 有向评价、场景硬门保守合取；`C_x,gw` 只补偿 paper-compatible score，不改变物理或 COLREG 硬判定。
- Step3 尚未完成；不进入 Step4，等待用户授权下一证据批次。

### Step3 · 第七批用户授权 [2026-07-28]

- 用户确认继续 Step3。
- 本批范围：BL-65、BL-66、BL-67、BL-68、BL-69。
- 目标：明确动态船体 footprint 与姿态插值、连续碰撞/搁浅检测及数值不确定性、安全域/CPA profile、负 TCPA/低相对速度语义，以及可用于 ENC clearance 的地图层。
- 本批只收集和登记证据；用户确认前不把盲区标为闭环，不进入 Step4，不实施代码。

### Step3 · 第七批中断交接 [2026-07-28]

- 本批尚未形成正式证据结论；BL-65..BL-69 保持“未调研”，不得视为闭环。
- 已完成但尚待整理的本地取证：
  - `models.py` 已有各船模 `ship_vertices`，但当前碰撞/搁浅判定未使用；Viknes 顶点外包尺寸与 `length/width` 存在小幅不一致。
  - `create_ship_polygon()` 使用通用五边形；`Simulator` 船间碰撞和搁浅仍主要依赖中心距/本船半长；`distance_to_enc_hazards()` 和 segment check 仍按点/中心线。
  - 当前 RK4 integrator 只返回区间终点，无 dense output；`head_on` 的 `dt_sim=0.5 s`，离散端点检测存在穿越风险。
  - CPA 至少有三套低相对速度阈值和返回语义：`evaluation/encounter.py`、`common/math_functions.py`、`common/miscellaneous_helper_methods.py` 不一致。
  - SeaCharts 2.2.0 把 `dybdeareal/grunne` 合为 seabed，把 `skjer/torrfall/landareal/ikkekartlagtsjomaltomr` 合为 shore；当前缓存 shapefile 不保留原始 layer provenance/CATZOC。
  - Romsdal GDB 使用 EPSG:25833；含 `dybdeareal`、`landareal`、`torrfall`、`grunne`、`skjer`、`dybdepunkt`、`datakvalitet`、`ikkekartlagtsjomaltomr`。`head_on` 路线穿过的 CATZOC 为 A1/A2，未与 land/torrfall/point shoal/unsurveyed feature 相交。
- 已定位外部主证据，下一对话需登记为新 R 条目并给出三类置信度：
  - Tang et al., C2A continuous collision detection：连续姿态插值、first time of contact、conservative advancement 和 motion bound。
  - Shapely 2.1.2 官方 manual/reference：平面 Cartesian 前提、`intersects` 包含边界接触、double precision 和 `set_precision` collapse 风险。
  - Kartverket/Geonorge `Sjøkart - Dybdedata` 产品规约：各 layer 几何/深度字段、CATZOC、位置精度和未测区语义。
  - IMO MSC.192(79)：CPA/TCPA preset limits 属可设置阈值；不能据此生成统一法规硬门。
  - Namgung 2022：标准相对运动 TCPA 公式及负 TCPA 表示 CPA 已通过。
- 候选整理方向，仅作交接草稿，不是裁决：
  - 物理 footprint 与 safety domain/buffer 分离；接触事实不加安全 buffer。
  - V1 使用同步时间的连续碰撞检测，禁止只做端点采样或把两条独立 swept union 相交直接判碰撞。
  - paper-compatible CPA 阈值保持历史绝对 profile；船尺度指标作为独立诊断/新 profile，不改论文复现参数。
  - `signed_tcpa`、future TCPA、observed CPA 分字段；负 TCPA 不单独解除 encounter，低相对速度显式标 undefined/status。
  - ENC 输出区分 polygon hazard clearance、point/line feature distance、unknown/unsurveyed overlap 和 CATZOC；不得宣称 operational UKC。
- 下一对话必须先复核工作树、读取本日志和 `design-grounding` Step3 规则，再完成 BL-65..BL-69 的正式证据登记；展示后停在用户确认门。

### Step3 · 第七批深度调研：动态 footprint、连续碰撞/搁浅、CPA/TCPA 语义与 ENC clearance [2026-07-28]

#### 取证摘要

- 主仓 `main` head `239aa22`、clean；worktree `codex/colav-backend-algorithms` head `67625e7`（较 checkpoint `7789a5f` 多 1 个 `feat(web): expose ENC safe-water polygons` commit，属 BL-69 相关只读 web 投影，不影响 BL-65..69 证据语义）、clean。
- 外部证据由 3 个并行 agent 取证，全部直读原始 PDF / 官方文档，未引用 SO / 博客 / 二手综述。已登记为 R51..R60。
- 本地代码复核覆盖 `core/models.py`、`core/integrators.py`、`simulator.py`、`common/map_functions.py`、`common/vessel_data.py`、`common/math_functions.py`、`common/miscellaneous_helper_methods.py`、`evaluation/encounter.py`。
- **源身份修正（已在 R51/R56/R58/R59 标注）**：
  - R51：`tang09.pdf` 实为 Tang/Kim/Manocha C²A（ICRA 2009），非任务描述的“Connectivity-Based Culling”论文；采用 C²A，符合 CCD 需求。
  - R56：MSC.192(79) 经核验为雷达设备标准（Annex 34）而非 ECDIS；ECDIS 标准为 MSC.232(82)。
  - R58：MSC.192(79) 用于 BL-67/68 时反而更切题（CPA/TCPA 告警属雷达/ARPA 标准）。
  - R59：Namgung 2022 实际标题为“Local Route Planning for Collision Avoidance of MASS…”，单作者非 et al.。

#### BL-65 · 动态船体 footprint、body reference、姿态插值与安全 buffer

- [R22] `models.py` 各船模 dataclass 已携带 `ship_vertices: np.ndarray`（Viknes/Telemetron/FCB45 三套），但当前碰撞/搁浅判定链路（`simulator.determine_ship_collision`、`determine_ship_grounding`、`distance_to_grounding`）**完全未使用** `ship_vertices`。
- 当前实际使用的 footprint 来自 `create_ship_polygon()`（`map_functions.py:475-507`）：以 `(x, y, heading, length, width)` 构造一个**通用五边形**（左后/左前/艏尖/右前/右后），而非船模自身 `ship_vertices`。它存在两处几何不一致：
  - 第 501 行 `x_max = x + eff_length/2 - eff_width`：x_max 隐含了“艏尖比艉前移一个 width”的假设，使矩形主体长 `eff_length - eff_width`，艏尖另加 `eff_width/2`。对 Viknes `length=8.45, width=2.71`，矩形长 `5.74 m`，艏尖长 `1.355 m`，与真实船体顶点分布不对应。
  - 第 503-505 行坐标元组以 `(y, x)` 顺序给出（north/east 混用），仅依赖后续 `affinity.rotate(..., origin=(y,x))` 补救；坐标轴约定脆弱。
- `simulator.determine_ship_collision`（`simulator.py:434-448`）以**中心距 `<= ownship.length/2`** 判定，不使用 `create_ship_polygon`、不使用目标船尺寸/姿态、不做姿态插值。
- `simulator.determine_ship_grounding` / `distance_to_grounding`（`simulator.py:450-473`）调用 `mapf.min_distance_to_hazards(..., ship_state[1], ship_state[0])`，即**中心点到 hazard 并集的距离 `<= ownship.length/2`**。同样是点-中心距离，不使用 footprint。
- [R51]（C²A, Sec I）：离散端点采样会漏掉步间碰撞（tunneling problem）；CCD 通过在两姿态间构造连续运动插值、沿插值路径检查相交，保证不漏报。C²A 的 first time of contact `t = min { t ∈ [0,1] : A(t) ∩ B ≠ ∅ }`（Sec III.A Eq.1），**边界接触计为碰撞**（非空相交包含 touching）。
- [R51]（Sec III.B）：C²A 假设 piecewise-constant 平移速度 `v` 与旋转速度 `w`，构造连续运动 `M(t)` 插值 `q_0 → q_1`；“when the simulation time-step is small, the difference between the actual objects' motions and the interpolated paths is negligible.” 对 Viknes `7 m/s、15 deg/s、dt=0.5 s`，该 piecewise-constant 假设可作为 oracle 的轨迹模型。
- [R51]（Sec IV Eq.3）：平移+旋转耦合的运动上界 `m = |v·n| + ∫ max_i |w·r_i(t)| dt + …`，轨迹由 **screw motion** 限定（比独立处理平移与旋转更紧）。**线性顶点插值（lerp）在旋转下会低估 swept volume**（Sec II.A 指出 SAT-based CCD“becomes overly conservative when there is a large rotational motion”），故 V1 oracle 不得用 lerp 顶点代替连续姿态插值。
- [R52]（Shapely manual）：`intersects` True 当“boundary or interior … intersect in any way”（边界接触计为相交）；`touches` 要求“at least one point in common and their interiors do not intersect”；`distance` 返回最小距离（float，0.0 即接触但受浮点相等敏感）；`buffer(distance)` 给物理接触 buffer；Shapely **仅支持平面 Cartesian**（“does not support coordinate system transformations”），任何 WGS84 lat/lon 必须先投影（UTM）再做几何查询。
- **物理 footprint 与 safety buffer 必须分离**：[R51] 的 first-TOC 定义纯几何接触事实；safety buffer（COLREG 安全域、near-miss 裕度）是独立风险指标，不得改写“是否实际接触”的事实定义。这与已闭环的 BL-53/BL-61 三层分离一致。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 每状态：用该船模型 `ship_vertices`（无 vertex 时 fallback 到 `create_ship_polygon`，并显式标记 fallback）构造定向 footprint，与该船 hazards/ENC bbox 做 `intersects`/`distance`。
  - 每区间：在 `t_k → t_{k+1}` 对位置和最短角差做连续姿态插值（piecewise-constant v/w，screw-motion bounded），用 C²A conservative advancement（[R51] Eq.2 `Δt = d(A,B)/m`）或可证明上界的自适应姿态细分，保证无 tunneling。
  - 接触事实定义不加 buffer；near-miss/safety domain 独立输出。
- 证据边界：
  - 可冻结的语义：footprint 必须用船模 vertex（或显式 fallback 五边形）；姿态插值必须连续（不得 lerp 顶点）；接触事实与 buffer 分离。
  - `UNKNOWN`：最大角点位移上界、自适应细分容差、`set_precision` 的 grid_size 数值仍属 BL-66；当前不得填固定厘米/米数。
- 状态：证据已登记，未标闭环，等待用户确认上述契约方向与 fallback 标记政策。

#### BL-66 · 连续碰撞/搁浅检测方法、first-contact、容差与数值不确定性

- [R29][R22] `core/integrators.py` 的 `erk4_integration_step`（`integrators.py:17-39`）**只返回区间终点 `x_next`**，无 dense output、无中间时刻状态、无连续解表示。`euler_integration_step` 同理。因此任一 `[t_k, t_{k+1}]` 区间内的连续碰撞检测只能由外层 oracle 自己做姿态插值/扫掠，integrator 不提供。
- [R51]（C²A, Sec I）：端点采样失效模式 tunneling——“Discrete algorithms check for collision only at sampled configurations … may miss collision between two successive configurations.”
- [R51]（Sec III.A Eq.2）：conservative advancement 步长 `Δt_i = d(A(t), B) / m`，其中 `d` 为最近距离下界、`m` 为单位时间运动上界；重复求和 `t = ΣΔt_i` 直到 `d(A(t),B) < 用户指定阈值`。**阈值由用户指定，标准未强制数值**。
- 保守上界（PROJECT_FACT 推导 + [R51] Eq.3）：给定 Viknes `7 m/s` 平移 + `15 deg/s` 旋转、`dt=0.5 s`，单步最远顶点位移上界 `≤ (|v| + |w|·r_max)·dt`，其中 `r_max ≈ length/2 = 4.225 m`。代入：`(7 + 0.2618·4.225)·0.5 ≈ 4.05 m/step`。即任一区间内顶点可扫过约 `4 m`；窄 hazard（< 4 m 宽）或步间穿透会被端点采样漏掉。这正是 BL-52 已记录的“canonical `7 m/s`、`dt=0.5 s` 每步平移约 3.5 m”的旋转增广版。
- [R52] `distance` 返回 float，0.0 为接触但受浮点相等敏感；`intersects` 边界接触计 True；`buffer(0)` 可清理 self-touching/bowtie polygon 但不改变接触事实。
- [R53]（`set_precision`）：`grid_size` 大于船体最小特征（beam/chine）时会**拓扑坍缩**——“Line and polygon geometries may collapse to empty geometries if all vertices are closer together than grid_size”；“Spikes or sections in polygons narrower than grid_size … will be removed。” 安全模式 `mode='valid_output'` 保证输出有效（坍缩元素被移除）；`mode='pointwise'` 可能输出无效几何。**Viknes beam=2.71 m，任何容差 grid_size 必须远小于 2.71 m**，否则船体多边形会被静默删除。输入几何必须先 `make_valid`。
- **禁止把两船 swept union 各自独立构造后相交来判定动态船碰撞**：swept union 是单体的扫掠体积；两船都在动时，必须在**同步时间**下对 `A(t)` 与 `B(t)` 做 CCD（[R51] Eq.1 是 `A(t) ∩ B(t) ≠ ∅`，二者共享同一 `t`）。各自独立构造 union 再相交会丢失时间同步，可能漏报（两船交替通过同一空间）或误报（不同时刻占用）。
- **numerical tolerance、chart uncertainty、safety buffer 三者必须分离**：
  - numerical tolerance：浮点/几何精度（`set_precision` grid_size、`distance==0` 判定），属 oracle 实现细节，不改接触事实。
  - chart uncertainty：CATZOC / 测量年代 / 未测区（[R55]/[R57]），属数据质量，不改 hazard 几何。
  - safety buffer：COLREG 安全域 / near-miss 裕度，属风险指标。
  三者不得合并为同一个 buffer。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 船间碰撞：同步时间 CCD，`physical_collision` 由 first-TOC 定义；`clearance_m` = 两 footprint 最小几何距离（接触后 0）。
  - 搁浅：每状态 footprint 与该船 hazards 做 `intersects`/`distance`；每区间做连续扫掠或自适应姿态细分（上界由运动学保证）。
  - 容差：`set_precision` grid_size 仅用于 near-touch 数值稳定性，必须 `<< beam`；接触事实判定不用 grid_size，用 `intersects`/`distance==0`。
  - 输入几何先 `make_valid`；`buffer(0)` 仅用于清理自交叉。
- 证据边界：
  - 可冻结的语义：同步时间 CCD、swept 不能跨时间独立相交、三类 buffer 分离、grid_size `<< beam`。
  - `UNKNOWN`：具体 grid_size 数值（如 1e-3 m？1e-6 m？）、自适应细分收敛阈值、`m` 上界的具体实现（C²A screw motion vs 简化线性上界）仍需实现期裁决；当前不得填固定常数。
- 状态：证据已登记，未标闭环，等待用户确认同步时间 CCD 与三类 buffer 分离。

#### BL-67 · 安全域及 preferred/minimum CPA：固定值与船尺度策略

- [R58]（MSC.192(79) Annex 34, §5.29.1/§5.29.2 与 CPA/TCPA 定义）：CPA/TCPA 限值为**操作员设置**——“Limits are set by the operator related to own ship”；dangerous target 定义为“violating the values as preset by the operator”。标准**未给固定数值**；grep 全文无任何米/海里固定 CPA 值。
- [R60]（COLREG Rule 8(a)(d)）：“positive, in ample time, with due regard to good seamanship”与“passing at a safe distance … finally past and clear”均为**定性表述**，无固定米值。
- [R59]（Namgung 2022, §2.3 Eq.7–13）：Fujii 族椭圆船域，**半轴随船长度 L 尺度**——基础模型（Fujii 1971）长半径 `4L`、短半径 `1.6L`；Namgung&Kim 2021 速度自适应扩展在 10 kt 基线下 `8L / 3.2L`。即文献中**唯一随船长度尺度的是船域（domain），不是 CPA 告警阈值**。
- 历史 `ccta_2023_demo` profile（[R25]/[R49]）使用**固定绝对值** `r_pref/r_min/r_nm/r_col = 190/100/50/30 m`。这些是论文研究者对模糊 COLREG 术语的解释，不是法规硬事实（[R2]/BL-61 已确认）。
- 证据支持的策略（DESIGN_CANDIDATE，非裁决）：
  - `paper_compatible` profile：**保持论文原始固定绝对 CPA 值**（如 `ccta_2023_demo` 的 190/100/50/30 m），不得按船长度缩放。缩放后即不再是论文复现。
  - `ship_length_scaled` profile（独立诊断/新 profile）：可用 Fujii/Namgung 椭圆船域（`a·L, b·L`），作为**独立**风险指标或新 profile，不替换 paper profile。
  - 两者并存，分 profile 报告；不得把缩放后的值仍称“论文复现”。
- 证据边界：
  - 可冻结的语义：paper profile 用固定绝对值；ship-length-scaled 用独立 profile；二者不混。
  - `UNKNOWN`：V1 默认采用哪个 profile、是否引入 Fujii/Namgung 数值（4L/1.6L vs 8L/3.2L）、是否做速度自适应，仍需 DP-21/DP-24 裁决。
- 状态：证据已登记，未标闭环，等待用户确认“paper 固定 / 船尺度独立”双 profile 策略。

#### BL-68 · 负 TCPA、CPA 已通过、低相对速度的统一语义

- [R59]（Namgung 2022, §2.1 Eq.1–5）：标准相对运动 CPA/TCPA 符号公式。符号约定 verbatim：“T_CPA can be zero, positive, or negative, and D_CPA can only be zero or positive. The closer both T_CPA and D_CPA are to zero, the higher the collision risk.” 负 TCPA verbatim：“A negative T_CPA means that the D_CPA has already passed, that is, the vessels are moving away from each other after the closest state.”
- [R59]（§4）：Namgung 在自身算法中把负 TCPA 用作“return to waypoint after collision-avoidance action”的触发——这是**论文特定的算法约定，不是 COLREG 规则**。证实：负 TCPA 是几何事实，不自动等同 encounter 解除。
- [R60]（Rule 8(d)）：“finally past and clear”是**持续核查义务**（“effectiveness … carefully checked until … finally past and clear”），不是释放触发。进一步证实 post-CPA ≠ encounter released。
- 当前代码三套 CPA 实现**语义不一致**（PROJECT_FACT）：
  - `evaluation/encounter.py:21-33` `cpa()`：`speed_sq < 1e-9` 时返回 `(distance, 0.0, 0.0)`——低相对速度静默标 TCPA=0；`tcpa_s = max(0.0, signed_tcpa)`——负值被截断为 0，丢失 post-CPA 信号；但同时保留 `signed_tcpa` 字段，是三者中最接近正确的。
  - `common/math_functions.py:54-74` `cpa()`：`v_AB_norm < 1e-6` 时返回 `(inf, inf)`——完全不同语义（无限大 vs 0）；不返回 signed tcpa。
  - `common/miscellaneous_helper_methods.py:434-458` `compute_vessel_pair_cpa()`：`t_cpa = -dot(r,v)/dot(v,v)`（可为负），但调用方 `check_if_situation_is_risky_enough()`（:374-375）用 `t_cpa < t_cpa_threshold`——**负值自动通过风险检查**，无显式 post-CPA 语义。
- [R59] **未论及** `V_r → 0` 奇点：Eq.4 除以 `V_r`，`V_r=0` 时公式未定义，但论文文本从未提及“TCPA → ∞”或“undefined status”。故低相对速度的显式状态标志**无文献支持**，属工程推断（DESIGN_DECISION）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 统一 CPA 实现：单一 `cpa()` 返回 `(signed_tcpa_s, future_cpa_m, observed_cpa_m, rel_speed_status)`。
  - `signed_tcpa_s`：可为负（[R59] Eq.4 符号）。
  - `future_cpa_m`：预测 D_CPA（[R59] Eq.5）。
  - `observed_cpa_m`：截至当前时刻已实现的最小距离（工程构造，非文献）。
  - `rel_speed_status`：`NORMAL | LOW | NEAR_STATIC`（工程决策，阈值待定；不引用 [R59] 为支持）。
  - `post_cpa`：`signed_tcpa_s < 0`（[R59] verbatim）。
  - 负 TCPA **不单独解除 encounter**：encounter 解除需结合 stage 回退（BL-71）与 COLREG 行为 predicate（BL-72..74）。
- 证据边界：
  - 可冻结的语义：signed tcpa、post-CPA 不自动解除 encounter、统一单一 CPA 实现。
  - `UNKNOWN`：低相对速度阈值（`LOW`/`NEAR_STATIC` 的 m/s 数值）、`observed_cpa_m` 的实现细节，仍需裁决。
- 状态：证据已登记，未标闭环，等待用户确认统一 CPA 语义与负 TCPA 不自动解除 encounter。

#### BL-69 · 可靠计算 ENC clearance 的地图层、未知区与数据质量边界

- [R54]（Kartverket Sjøkart-Dybdedata v20201001, §5.1.2）：各 layer 几何/字段/可航语义 verbatim 表：

  | Feature (verbatim) | 几何 | 关键字段 | S-57 等价 | 可航语义 |
  |---|---|---|---|---|
  | `Dybdeareal` | Polygon (MultiPolygon) | `minimumsdybde`(DRVAL1), `maksimumsdybde`(DRVAL2) | DEPARE | 深度区间内的可航水域 |
  | `Dybdekurve` | Line (MultiLineString) | `dybde` | DEPCNT | 等深线（线，非面） |
  | `Dybdepunkt` | Point | `dybde`, `dybdetype` | SOUND | 离散测深点（点，非面） |
  | `Grunne` | Point | `dybde` | UWTROC | 浅点/礁（点特征，非面） |
  | `IkkeKartlagtSjømåltOmr` | Polygon (MultiPolygon) | 无 | UNSARE | **未测区** |
  | `Landareal` | Polygon | 无 | LNDARE | 不可航（陆地） |
  | `Skjær` | Point | 无 | — | 不可航，点 |
  | `Tørrfall` | Polygon | 无（边界为海图零点下 0.5 m） | DEPARE(潮间带) | 不可航潮间带 |
  | `Datakvalitet` | Polygon | `CATZOC` | M_QUAL | CATZOC 质量面 |
  | `MudretOmråde` | Polygon | `minimumsdybde`, `maksimumsdybde` | — | 维护深度疏浚区 |

- [R54]（§5.1.2.41 `codeList Catzoc`）：A1/A2/B/C/D/U 六类定性语义 verbatim。A1=“Full flatedekning oppnådd. Alle signifikante objekter funnet og dybder målt.”；B=“Full flatedekning ikke oppnådd. Uoppdagede objekter farlig for navigasjon forventes ikke, men kan forekomme.”；U=“Ikke vurdert”。**定量位置/深度精度表不在 Kartverket 页面**，在 IHO S-52 APP2 / S-57 Ch.2，本批授权源未含，标 `EXTERNAL_CONFIRMATION_REQUIRED`。
- [R55]（Kartverket CATZOC NO+EN 页面）：与 [R54] codeList 一致；Kartverket 建议“navigere med varsomhet i områder med eldre dybdemålinger med lav kvalitet”。
- [R56]（MSC.232(82)）：ECDIS 强制 ENC 为图数据源（§3.2/§4.1）；§5.8 mandates **safety contour alarm**（操作员选择，默认 30 m 仅显示回退）；§5.9 safety depth 仅控制测深点显示强调；**全文无 CATZOC/UKC/squat/chart-quality buffer 强制数值**。30 m 是告警默认回退，非物理 clearance 规则。
- [R57]（S-57 Ch.1）：DEPARE 定义“a water area whose depth is within a defined range of values”，深度区间由 `DRVAL1/DRVAL2` 定义——**面积平均深度带，非连续海床场**。UNSARE（code 154）“An area for which no bathymetric survey information is available”，无任何深度属性。M_QUAL（code 308）是携带 CATZOC/POSACC/SOUACC 的 meta-object，是质量面而非 hazard。DEPCNT（code 43）“often represent an approximate location of the line of equal depth”——线特征，显式近似。
- 本地 SeaCharts 2.2.0 layer 分组（`seacharts/spatial/layers.py:8-38`，[R35] 已审计）：`seabed = dybdeareal + grunne`（按 `minimumsdybde/dybde` 重分箱）；`land = landareal`；`shore = skjer + torrfall + landareal + ikkekartlagtsjomaltomr`。两处与 [R54] 规约的偏差：
  - `grunne` 按 [R54] 是 **Point**（UWTROC 浅点），SeaCharts 却喂入 `seabed`（多边形深度区集合），实际把每个浅点当零面积深度条目。这是模拟器约定，非海图语义。
  - `shore` 把 `ikkekartlagtsjomaltomr`（UNSARE 未测区）折叠进 shore/不可航类。对 V1 hazard 模型**保守**（未知当不可航），满足“未测区不得静默当安全”；但混淆了“未测”与“陆地/岸”，下游无法仅凭 `shore` 几何区分二者。若需独立报告未测区，须直接读 `ikkekartlagtsjomaltomr` 而非经 `enc.shore`。
- 当前 `distance_to_enc_hazards`（`map_functions.py:749-773`）用 `Point(x,y).distance(hazard)`——**中心点到 hazard 并集的距离**，不是 footprint clearance。`extract_relevant_grounding_hazards_as_union()`（:548-579）会 `land.union(shore).union(dangerous_seabed)` 并删除 Polygon interior，可能把 geometry hole 填成 hazard（[R38] 已记录，BL-52）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - **polygon hazard clearance**：`Dybdeareal`/`Tørrfall`/`MudretOmråde`（深度区间多边形）+ `Landareal`/`Skjær`(点需 buffer)/` Shore`，按该船静态吃水独立派生 hazards；footprint 与 hazards 做 `intersects`/`distance`。
  - **point/line feature distance**：`Dybdepunkt`/`Grunne`/`Dybdekurve` 仅作独立距离诊断，**不得 buffer 后称为真实 hazard 边界**（除非有显式版本化 buffer 政策）。
  - **unknown/unsurveyed overlap**：`IkkeKartlagtSjømåltOmr`（UNSARE）单独输出为 `unknown_area_overlap` 标志，不得静默当安全；保留保守 shore 折叠为可选，但报告层须能区分未测区。
  - **CATZOC quality flag**：作为序数质量标签（A1→U），不作为数值 buffer 源；数值精度表标 `EXTERNAL_CONFIRMATION_REQUIRED`。
  - **chart-geometric clearance only**：不得宣称 operational UKC（需潮汐/squat/heel/动态吃水，[R37]/BL-51 已确认）。
- 证据边界：
  - 可冻结的语义：polygon/point-line/unknown/CATZOC 四类分离；每船独立派生 hazards；不宣称 UKC。
  - `UNKNOWN`：`Skjær` 点是否需要 buffer、`MudretOmråde` 是否纳入 V1 hazards、未测区是否独立 hazard 还是仅标志，仍需裁决。
- 状态：证据已登记，未标闭环，等待用户确认四类分离与未测区独立报告。

#### 本批用户确认门

- 待用户分别确认 BL-65、BL-66、BL-67、BL-68、BL-69 的证据是否回答原问题。
- 建议确认口径：
  - BL-65：footprint 用船模 vertex（无 vertex 时显式 fallback 五边形）；姿态插值连续（不得 lerp 顶点）；接触事实与 safety buffer 分离。
  - BL-66：同步时间 CCD（禁止跨时间独立 swept union 相交）；numerical tolerance / chart uncertainty / safety buffer 三类分离；`set_precision` grid_size `<< beam`；具体数值容差后置。
  - BL-67：paper profile 保持固定绝对 CPA；ship-length-scaled 船域作为独立 profile；缩放后不称论文复现。
  - BL-68：统一单一 CPA 实现返回 signed tcpa/future cpa/observed cpa/rel-speed status；负 TCPA 不自动解除 encounter；低相对速度为工程决策。
  - BL-69：polygon/point-line/unknown/CATZOC 四类分离；每船独立派生 hazards；不宣称 operational UKC；未测区独立报告。
- 未确认前不改盲区为“已闭环”，不进入 Step4，不实施代码。

### Step3 · 第七批证据用户确认 [2026-07-28]

- 用户确认本批全部证据。
- BL-65 边界闭环：footprint 用船模 vertex（无 vertex 显式 fallback 五边形）；姿态插值连续（不得 lerp 顶点）；接触事实与 safety buffer 分离；平面几何须投影 UTM；具体数值容差后置。
- BL-66 边界闭环：同步时间 CCD（禁止跨时间独立 swept union 相交）；numerical tolerance / chart uncertainty / safety buffer 三类分离；`set_precision` grid_size `<< beam`；具体数值后置。
- BL-67 边界闭环：paper profile 保持固定绝对 CPA；ship-length-scaled 船域作独立 profile；缩放后不称论文复现；V1 默认 profile 待 DP-21/DP-24 裁决。
- BL-68 闭环：统一单一 CPA 实现（signed tcpa / future cpa / observed cpa / rel-speed status）；负 TCPA 不自动解除 encounter；低相对速度为工程决策，阈值后置。
- BL-69 边界闭环：polygon / point-line / unknown / CATZOC 四类分离；每船独立派生 hazards；不宣称 operational UKC；未测区独立报告；`Skjær` buffer 等细节后置。
- 用户授权加速路径：**路径 1** —— B 档（TD-01 接口设计裁决，BL-05,10..38 共 29 项）+ C 档（Worker/证据包/Web schema 工程裁决，BL-90..108,114..118 共 24 项）批量合并裁决或授权后置；A 档（COLREG 行为 / 任务指标 / 资格门 / 统计 / PSB·RLMPC 归一化，BL-70..89,109..113 共 30 项）保持 primary-source 深度调研。
- Step3 尚未完成；不进入 Step4。

### Step3 · 第八批深度调研：COLREG 行为 Oracle 分类角、阶段锁定、行为阈值、通过侧几何与多船 Rule 17 [2026-07-28]

#### 取证摘要

- 本批为 A 档深度调研第一组，对应 DP-22 COLREG 行为 Oracle 的 BL-70..74。
- 外部 primary source 由单一 agent 串行取证 8 个源，全部 verbatim 引用：[R61] IMO COLREGS 条约文本、[R62] Woerner 2016 MIT PhD（canonical classification + behavioral thresholds，全文 16 MB）、[R63] Woerner 2019 Autonomous Robots（论文版）、[R64] Eriksen 2020 Frontiers（FSM 锁定/释放）、[R65] Hagen 2022 J. Navigation（AIS 实证）、[R66] Akdag 2022 IFAC CAMS、[R67] Murray & Naeem 2024 arXiv、[R68] Zhao & Roh 2019（仅摘要）。
- **Hagen 2023（Ocean Engineering 288:115991，本项目的 load-bearing paper）全文付费墙且无 preprint/author-accepted-manuscript**。可归因于 Hagen 2023 的内容仅来自 [R67] 的引用片段、2024 follow-up 与项目自身标记 `numerical_reproduction_confirmed=False` 的重建实现。凡仅可推断的 Hagen 数值，标 INFERENCE，不得当作 Hagen 原始数值引用。
- **跨 BL 核心发现**：COLREGS 条约仅提供一个角度——Rule 13(b) "more than 22.5 degrees abaft her beam"（源于 Rule 21 灯光弧几何），其余所有阈值（head-on 半角、overtaking contact-angle 容差、crossing-ahead band、substantial/detectable 度数、Stage 距离倍数、Rule 17(a)(ii) 触发）均为 versioned engineering choice。三个 A-grade source 给出三个不同 head-on 半角（Woerner 13° / Eriksen-Tam&Bucknall 22.5° / Murray 5°）。Playground oracle 必须是 **profile-parameterized** 工件，不是单一硬编码分类器。

#### BL-70 · Rule 13/14/15 分类角与边界 profile

- [R61] IMO Rule 13(b) verbatim："A vessel shall be deemed to be overtaking when coming up with another vessel from a direction **more than 22.5 degrees abaft her beam**"。该 22.5° 来自 Rule 21 灯光弧（舷灯弧 112.5° from ahead → beam 在 112.5° → abaft-beam 始于 112.5° = 22.5° abaft beam）。**这是条约唯一固定的角度，且是灯光几何，非遭遇规则**。
- [R61] IMO Rule 14(a)："two power-driven vessels are meeting on **reciprocal or nearly reciprocal courses**"——"nearly" 未定义；Rule 14(c)："When a vessel is in any doubt... she shall assume that it does exist"。Rule 15："the vessel which has the other **on her own starboard side** shall keep out of the way"——**无任何角度**。
- [R62] Woerner 2016 Algorithm 5 (p.145) verbatim 默认值：`αcrit_13`（overtaking tolerance）= **45°**；`αcrit_14`（head-on tolerance）= **13°**；`αcrit_15`（crossing aspect limit）= **10°**。p.145 明示 "all αcrit values are configurable by evaluator"，Figure 4-7 caption (p.151)："All critical contact angles are configurable to the evaluator **as they have no prescribed value in the COLREGS**"。
- [R62] Woerner 分类是**双变量**（relative bearing β₀ ∈ [0,360) AND contact angle α₀ ∈ [-180,180)），非单变量。Head-on（Algorithm 5 line 12-13）：`|β₀| < αcrit_14 AND |α₀| < αcrit_14`——bearing 和 course-difference 都须在 head-on cone 内（默认 13°）。故 head-on 区是 2D cone，非 bearing slice。Overtaking（line 7）：`β₀ > 112.5 AND β₀ < 247.5 AND |α₀| < αcrit_13(45°)`——astern 135° wedge 且 gated by contact angle；若 contact 指向横穿（|α₀|>45°）则为 crossing 非 overtaking。
- [R64] Eriksen 2020 §4.2.3 + Figure 5 caption：使用对称区域 `θ₁,θ₂,θ₃ = [22.5, 90, 112.5°] offset from ahead`，并引用 Tam & Bucknall (2010) 推荐"larger region of **22.5°** in order to increase robustness"。故 Eriksen head-on 用 **±22.5°**，宽于 Woerner 13°。
- [R67] Murray & Naeem 2024 Eq.(11) verbatim：HO `(0≤β≤5)∨(355<β<360)∨(|Δψ|≤5)`；SB `(5<β≤112.5)∧(|Δψ|>5)`；OT `(112.5<β≤247.5)∧(Δψ>5)`；PS `(247.5<β≤355)∧(|Δψ|>5)`。Head-on 此处 **±5°**，窄于 Woerner。
- **三 A-grade source 给三个不同 head-on 半角（5°/13°/22.5°）** → 证实该角度是 versioned profile choice，非法规事实。112.5° crossing/overtaking 边界源于 Rule 21 灯光弧，是 regulatory constant。
- [R48] PROJECT_FACT：当前 `evaluation/encounter.py:56` 用 `|relative_bearing| ≤ 15.0 AND course_difference ≥ 150.0` 判 head-on。15° 不同于 Woerner 13°；单变量 bearing-only 测试丢弃了 Woerner 的 contact-angle gate；crossing 边界 `±112.5`（:58,:60,:62）匹配 regulatory 值；重建 evaluator 完全未算 contact angle α。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 112.5° crossing/overtaking 边界作 regulatory constant。
  - head-on 半角与 overtaking/contact-angle 容差作显式 profile 参数，Woerner 默认（13°/45°/10°）。
  - 采用**双变量 (β, α) 分类**而非 bearing-only。
  - 暴露 Tam&Bucknall 22.5° 与 Murray 5° 为命名 alternative profiles。
- 证据边界：可冻结"profile-parameterized + 双变量"；具体 V1 默认角度（Woerner 13° vs Eriksen 22.5°）待 DP-22 裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-71 · encounter 阶段、规则锁定、解除与再次进入

- [R61] IMO Rule 13(d) verbatim："Any subsequent alteration of the bearing... shall not make the overtaking vessel a crossing vessel... or relieve her of the duty of keeping clear of the overtaken vessel **until she is finally past and clear**"。Rule 8(d)："The effectiveness of the action shall be carefully checked **until the other vessel is finally past and clear**"。**"past and clear"无数值定义**。
- [R64] Eriksen 2020 §4.2.1 verbatim：rule assignment 是 state machine，状态 SF/OT/HO/GW/SO/EM。"**all transitions have to go either from or to the safe state. This implies that when the state machine decides that a [rule] situation exists... it will not allow switching to another state without the situation being considered as safe first.**"——**锁定行为**：船不能通过机动逃离角色；须先满足 exit（释放）到 SF 才能重分类。
- [R64] Eriksen Eq.(12) verbatim：`entry_i = true if d_CPA < d_CPA^{i,enter} ∧ t_CPA ∈ [t_CPA^{i,enter}_lo, t_CPA^{i,enter}_hi]`，i ∈ {SO,OT,GW,HO}。**进入 active encounter 须 DCPA 低于阈值 AND TCPA 在窗口内**，非单纯 range。
- [R64] Eriksen EM entry：`entry_EM = true if t_crit < t_crit^{EM,enter} ∧ t_CPA > 0`（t_crit = "time until obstacle enters d_crit boundary"，Eq.11），仅从 geometrical GW/HO（"overtaking represents smaller danger"）。
- [R64] Eriksen Eq.(13) verbatim：`exit_i = true if d_CPA ≥ d_CPA^{i,exit} ∨ t_CPA ∉ [t_CPA^{i,exit}_lo, t_CPA^{i,exit}_hi]`，且 "**other thresholds in order to implement hysteresis to avoid shattering**"——entry 与 exit 阈值故意不同，防抖动。
- [R48] PROJECT_FACT：当前 `encounter.py:76-87` `stage_timeline` 用**纯 range gate**（Stage 1 `≤ 8×safety_distance`，Stage 2 `≤ 4×safety_distance`，Stage 3 = post-CPA），是 range-only 近似，**省略了 Eriksen/Hagen 的 DCPA/TCPA gating**。`EncounterMonitor.update`（:149）用 `signed_tcpa_s ≤ 0` 判 Stage 3，符合精神但无 hysteresis。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 锁定 FSM 模仿 Eriksen 2020 §4.2（SF↔{OT,HO,GW,SO,EM}，强制 return-to-SF）。
  - entry/exit 阈值基于 (DCPA, TCPA, t_crit)，含显式 hysteresis。
  - Stage 1/2/3/4 作为**独立 evaluation timeline**（post-hoc scoring），与**control state machine**（real-time role lock）分开。
  - release criterion 显式 versioned；默认 Eriksen 式 `d_CPA ≥ d_CPA^exit ∨ t_CPA < 0`。
- 证据边界：可冻结"锁定 FSM + hysteresis + 控制态与评价态分离"；Hagen Stage 1/2/3/4 的具体倍数（8×/4×）来自项目重建，未经 Hagen 2023 原文确认，标 INFERENCE。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-72 · "及时明显"与 stand-on 保向保速的量化阈值

- [R61] IMO Rule 8(a) verbatim："shall... be **positive, made in ample time** and with due regard to the observance of good seamanship"。Rule 8(b)："shall... be **large enough to be readily apparent** to another vessel observing visually or by radar; a succession of small alterations... should be avoided"。Rule 8(c)："**substantial** and does not result in another close-quarters situation"。Rule 16："**early and substantial action** to keep well clear"。**无一量化** "ample/substantial/readily apparent/early"。
- [R62] Woerner 2016 Algorithm 12 (Delayed Action) verbatim：`r_detect = range at detection (default 1.8·R_pref)`；`r_maneuver = range at ownship maneuver`；penalty `R_delay = R_delay^{max} · (r_detect − r_maneuver)/(r_detect − r_cpa)`。**"timely" 操作化为 maneuver range 相对于 detection range 与 CPA range，非固定 TCPA**。
- [R62] Woerner Algorithm 14 verbatim：`θ_app = apparent course deviation threshold (default 30°)`；`θ_md = minimum detectable course deviation (default 0°)`；penalty 从 `θ_md` 线性 ramp 到 `θ_app` 后平台。Default `R_θ_app^{max} = 50%`。**30° "readily apparent" 是默认值，可配置**。
- [R62] Woerner p.154 verbatim："The size of a readily apparent maneuver is not explicitly defined in the COLREGS, though **turns of 30° have been determined by custom to be sufficient**. **Some texts suggest a minimum of 35°**." 故文献锚定 "substantial" 在 **30-35°**（admiralty custom）。
- [R62] Woerner Algorithm 15（speed change）：`Δv = apparent speed reduction threshold (default 50%)`。"apparent" 速度变化 ≈ **初始速度的 50%**。
- [R62] Woerner Algorithm 16（stand-on maintain）verbatim：`θ_md = minimum detectable heading deviation (default 2°)`；低于 θ_md 无 penalty；高于 `θ_app(30°)` 平 max penalty `R^{max}(default 50%)`；中间线性。p.163 verbatim："**course changes greater than some threshold noise level (say, 2°) must be penalized** for stand-on vessels not otherwise invoking Rule 17.a.ii. Some small heading change up to the generally accepted substantial value of **30° must be increasingly penalized**."
- [R61] IMO Rule 17(a)(i)："the other **shall keep her course and speed**"。[R62] Woerner p.162：case law 解释为 "steady, predictable maneuver"——常规航行变更（如减速等引航员）豁免，但无解释的变更属违规。
- [R48] PROJECT_FACT：当前 `evaluator.py` 用 `|Δψ| ≥ 5°` OR `|ΔV| ≥ 0.1·V₀` 检测机动；"substantial" 在 `Δψ = 15°` 饱和；stand-on S17 对 pre-CPA 变更用 `10°` cap；P_sts 与 C_x_gw 在 15° 饱和。**这些非 Woerner 默认（30° substantial, 2° detectable）**，是重建者自选值。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 暴露四个 versioned 阈值/profile：`θ_detectable`（默认 2°）、`θ_substantial`（默认 30°）、`Δv_substantial`（默认 0.5）、`t_early_factor`（maneuver range 相对 detection range，Woerner Algorithm 12）。
  - "timely" 实现为 **range-fraction**（`r_maneuver / (r_detect − r_cpa)`）而非 raw TCPA，匹配 Woerner。
  - stand-on scoring 用同一 θ_detectable/θ_substantial ramp。
- 证据边界：可冻结"四阈值 profile + range-fraction timely"；当前代码 5°/15° 与 Woerner 2°/30° 的偏差须在重建时显式裁决采用哪套。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-73 · port-to-port、crossing ahead、passed clear 的几何判定

- [R62] Woerner §3 Eq.3.15：CPA pose 定义为 pair `Φ_cpa = [α_cpa, β_cpa]`——contact angle AND relative bearing at CPA，联合。p.87 verbatim："Contact angle refers to the **relative bearing of ownship as seen from the perspective of the contact**... Relative bearing (β) henceforth refers to ownship's relative perspective of the contact; contact angle (α) refers to the contact's relative perspective of ownship." **双视角几何**区分 port-to-port vs starboard-to-starboard。
- [R62] Woerner Eq.4.12 verbatim（port-to-port reward）：`R^{14}_{Φ} = [½(sin(α_cpa)+1)] · [½(sin(β_cpa)+1)] · R_max`。p.155 verbatim："A true port-to-port passage will be a relative bearing of **β = 270°** and a contact angle of **α = −90°**." 即 port-to-port = {(α_cpa, β_cpa) near (−90°, 270°)}；signed-sine reward 在此处最大。**这正是 signed cross-product/dot-product predicate**：sin(β) 与 sin(α) 编码 signed lateral geometry。
- [R62] Woerner §4.5.1 Rule 15 verbatim（crossing-ahead）："Crossing give-way vessels are specifically required to not cross ahead of the stand-on vessel... a stern crossing or near-stern crossing will result in a **narrow or negative contact angle** if the stand-on vessel does not maneuver." Penalty verbatim："penalize crossing ahead (e.g., **−25° < α_cpa < 165°** (configurable) where α_cpa is the stand-on vessel's contact angle if no action is taken under Rule 17.a.ii)." 故 crossing-ahead 经 **stand-on vessel 的 contact angle** α 在其 beam 前方（可配置 band 内）检测。
- [R61] IMO Rule 13(d)/8(d) "finally past and clear" 无数值。[R62] Woerner 经 **CPA 已发生**（t_CPA passed）AND range opening（signed t_CPA<0）AND overtaker 的 contact angle 移向 astern 检测 passed-and-clear；Algorithm 6（Rule 13/16）检查 "duty of keeping clear ... until past and clear" via pose at CPA。[R64] Eriksen Eq.(13) 给数值释放：`d_CPA ≥ d_CPA^exit ∨ t_CPA ∉ [lo,hi]`，t_CPA<0 表 "obstacle moving further away"。
- [R48] PROJECT_FACT：当前 `encounter.py:51` 算 `relative_bearing_deg`（signed）编码 port/starboard；但 `evaluator.py` **完全未算 contact angle α**。无 α 则 port-to-port pose scoring 与 crossing-ahead 检测无法忠于 Woerner/Hagen——重建 S14 仅用 starboard course change（:165），非 (α,β) pose reward。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 同时算 β（target 相对 ownship 的 bearing）与 α（ownship 相对 target 的 bearing = β+180°）。
  - crossing-ahead：`α_target ∈ [α_ahead_lo, α_ahead_hi]`（Woerner 默认 −25°..165°，可配置）。
  - port-to-port：Woerner Eq.4.12 signed-sine pose reward。
  - "passed and clear"：`{t_CPA<0 (signed)} ∧ {range increasing} ∧ {role's CPA-pose satisfied}` 合取，非固定 astern bearing。
- 证据边界：可冻结"双变量 (α,β) + signed-sine + 合取释放"；具体 α_ahead band 待 profile 裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-74 · multi-ship 规则冲突、非合作目标与 Rule 17 紧急阶段

- [R61] IMO Rule 17 verbatim 三阶段：(a)(i) "shall **keep her course and speed**"；(a)(ii) "**may however take action**... as soon as it becomes apparent to her that the vessel required to keep out of the way is not taking appropriate action"；(b) "When... she finds herself **so close that collision cannot be avoided by the action of the give-way vessel alone**, she **shall take such action as will best aid to avoid collision**"；(c) "shall... **not alter course to port** for a vessel on her own port side"；(d) "does not relieve the give-way vessel"。**三阶段触发器均定性**。
- [R62] Woerner Algorithm 11（Rule 17）verbatim：`if in extremis then compensate for maneuvers required in extremis`；对 power-driven crossing `penalize port maneuvers for port contacts`。p.162 verbatim："Stand-on vessels failing to maneuver prior to a collision have repeatedly been found partially (usually **25%**) at fault by admiralty courts when not invoking this clause [Rule 17.a.ii]." §II(a)/(b) 触发检测留 "reasonable and consistent criteria"，**Woerner 未固定 DCPA/TCPA 数值，可配置**。
- [R64] Eriksen EM state verbatim：`entry_EM = t_crit < t_crit^{EM,enter} ∧ t_CPA > 0`，仅从 GW/HO。这是 Rule 17(b) "shall act" 的工程实例化。
- [R62] Woerner §1.3.2 verbatim（non-cooperative）："Assertion: Evaluation algorithms can identify a vehicle not complying with the rules (protocol agnostic or collision agnostic) **using only track data**." §4.7 验证（Scenarios E-G: protocol agnostic / collision agnostic / dead in water）。p.163：stand-on 检测到 give-way non-compliant 则 "allowed and required... to take action"（Rule 17.a.ii）。**非合作处理 = stand-on 提前触发 Rule 17.a.ii；non-compliant target 按*应*遵守的规则评分**，post-hoc 可从 track 数据检测（give-way 的 S8/S15 崩溃）。
- **multi-ship 冲突解决——COLREGS 无统一规则**。[R61] Rule 18 给 vessel-type hierarchy（NUC > RAM > fishing > sailing > power-driven），非几何优先级。Rule 13(d) 说 overtaker 无论 bearing 漂移仍是 overtaker。**条约无"两个 give-way 义务同时存在"的规则**。
- [R62] Woerner（multi-contact thesis）：经 **priority weights** on each contact's CPA-utility（Fig 3-5 step/linear/quadratic）在单一 objective 求和解决 multi-contact——**非 rule hierarchy**。p.31："multi-objective optimization refers to... a single objective function... composed of components." 故 canonical multi-contact 工作也未定义 COLREGS-compliant 优先级，而是 objective weighting。
- [R68] Zhao & Roh 2019（仅摘要）："A novel strategy is used to solve the problem of **prioritizing/conflict resolution among multiple encountering vessels**" via DRL——**控制器策略，非 evaluation rule，非 COLREGS 文本**。
- [R67] Murray & Naeem 2024 §III：扩展至 "generic situation awareness where TVs manoeuvre according to other vessels... and not only according to OS-TV obligations"——概率性，非确定性 COLREGS 规则。
- C_x,gw：[R48] PROJECT_FACT 重建 `evaluator.py:173` `C_x_gw = clip(port_change / 15°, 0, 1)`——penalize give-way 转向 port（可补偿被迫行动的 stand-on）。**15° 饱和与 port-only 方向是重建者选择，非确认的 Hagen 值**。[R62] Woerner Algorithm 10 line 6（"penalize for hindrance of stand-on vessel"）是概念基础。
- [R48] PROJECT_FACT：当前 `evaluator.py` **无 Rule 17 phase machine**——`crossing_stand_on`（:174-179）把 S17 算成单一 pre-CPA-change penalty；无 "give-way not acting" 或 "collision unavoidable by give-way alone" 检测；无 EM state；非合作目标未建模（每个 target 假设合作）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - Rule 17 实现为每 stand-on pair 的三阶段 sub-FSM：KEEP → MAY_ACT（触发：paired give-way 的 S8 低于阈值且持续窗口）→ SHALL_ACT（触发：t_crit 低于 EM 阈值，Eriksen 式）；Rule 17(c) port-turn prohibition 仅在 MAY/SHALL 阶段对 port-side contacts。
  - multi-ship：**不发明 COLREGS 优先级**——采显式立场：paper_compatible 仅支持 per-pair evaluation + C_x,gw compensation；multi-ship 冲突解决属 regulatory scope 之外，引用 [R68] Zhao & Roh 2019 作为 controller-side（非 oracle-side）参考。
  - 非合作 target = 自身 S_* 低于 compliance threshold 的 target；oracle 标记并允许其 paired stand-on 提前进入 MAY_ACT（操作化 Rule 17.a.ii "becomes apparent"）。
- 证据边界：可冻结"Rule 17 三阶段 sub-FSM + multi-ship 不发明优先级 + 非合作 = S_* 阈值"；具体 compliance threshold、t_crit^EM 数值待 profile 裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

#### 本批用户确认门

- 待用户分别确认 BL-70、BL-71、BL-72、BL-73、BL-74 的证据是否回答原问题。
- 建议确认口径：
  - BL-70：oracle 为 profile-parameterized；112.5° 作 regulatory constant；head-on 半角与 contact-angle 容差作显式 profile 参数（Woerner 默认 13°/45°/10°）；采用双变量 (β,α) 分类；暴露 alternative profiles。
  - BL-71：锁定 FSM（Eriksen 式 SF↔{OT,HO,GW,SO,EM}）；entry/exit 含 (DCPA,TCPA,t_crit) hysteresis；control state machine 与 evaluation timeline 分离。
  - BL-72：四阈值 profile（θ_detectable 2°、θ_substantial 30°、Δv_substantial 0.5、t_early_factor range-fraction）；当前代码 5°/15° 偏差须裁决。
  - BL-73：双变量 (α,β) pose；crossing-ahead 经 stand-on 的 α；port-to-port 经 signed-sine reward；passed-clear 为合取（t_CPA<0 ∧ range increasing ∧ CPA-pose satisfied）。
  - BL-74：Rule 17 三阶段 sub-FSM；multi-ship 不发明优先级（per-pair + C_x,gw）；非合作 = S_* 阈值触发 stand-on MAY_ACT。
- 未确认前不改盲区为“已闭环”，不进入 Step4，不实施代码。

### Step3 · 第八批证据用户确认 [2026-07-28]

- 用户确认本批全部证据。
- BL-70 边界闭环：oracle 为 profile-parameterized；112.5° 作 regulatory constant；head-on 半角与 contact-angle 容差作显式 profile 参数（Woerner 默认 13°/45°/10°）；采用双变量 (β,α) 分类；alternative profiles 后置。
- BL-71 闭环：锁定 FSM（Eriksen 式 SF↔{OT,HO,GW,SO,EM}）；entry/exit 含 (DCPA,TCPA,t_crit) hysteresis；control state machine 与 evaluation timeline 分离；Hagen Stage 倍数标 INFERENCE。
- BL-72 边界闭环：四阈值 profile（θ_detectable 2°、θ_substantial 30°、Δv_substantial 0.5、t_early_factor range-fraction）；当前代码 5°/15° 偏差须裁决。
- BL-73 闭环：双变量 (α,β) pose；crossing-ahead 经 stand-on 的 α；port-to-port 经 signed-sine reward；passed-clear 为合取（t_CPA<0 ∧ range increasing ∧ CPA-pose satisfied）。
- BL-74 边界闭环：Rule 17 三阶段 sub-FSM；multi-ship 不发明优先级（per-pair + C_x,gw）；非合作 = S_* 阈值触发 stand-on MAY_ACT；compliance/EM 数值后置。
- 用户授权：可复制 `/Users/marine/Code/MASS-L3-Tactical Layer/.nlm` 配置，用 `/nlm-ask` 查询已有领域笔记本（colav_algorithms / maritime_regulations / safety_verification 等）加速调研。配置已复制到 worktree。
- Step3 尚未完成；不进入 Step4。

### Step3 · 第九批深度调研（B 档第一批）：TD-01 Custom MPC 插件契约 — DP-05/08/09/10 接口盲区批量裁决 [2026-07-28]

#### 取证摘要

- 本批为路径 1 加速的 B 档第一批：TD-01（Custom MPC 插件契约）的 DP-05 剩余项 + DP-08/09/10 接口设计盲区，共 17 项（BL-05, BL-10..21）。
- 与 A 档不同，本批盲区多为接口设计裁决（字段名/schema/容差/时间锚点），不依赖外部 primary source，主要证据来自 PROJECT_FACT（当前 `ICOLAV`、`PlannerTrace`、`PlanDiagnostics`、`RunSpec`、`SeedBundle`、`custom_mpc_adapter` 代码）+ Step2 已确认的 grilling 结论（DP-08..10）。
- 证据分层：PROJECT_FACT 为现有脚手架事实；DESIGN_CANDIDATE 为基于脚手架 + grilling 的设计候选；UNKNOWN 为仍需裁决的数值。
- **当前 `custom_mpc_adapter.py`（guidance 层 `IGuidance`）不是 `ICOLAV`**：它无 PlannerTrace、PlanStatus、solve_id、algorithm identity；其 `plan()` 签名只有 `obstacles: list[dict]`，无 covariance/enc/seed；所有 wrapper（PSBMPC/AcadosMPC/RRTStar）用 `except Exception → fallback SimpleLinearMPC`。这佐证 ALT-04（legacy custom_mpc_adapter 不得作正式接口）。正式 Custom MPC 须走 `CustomMPCAdapter(ICOLAV)` 薄适配器。
- **当前 `ICOLAV.plan()` 已返回 `9xN` 并接收 `do_list` 含 covariance**：脚手架比 `custom_mpc_adapter` 更接近正式契约。但 `do_list` 是裸元组 `(ID, state, covariance, length, width)`，不自描述状态顺序、协方差坐标系、量测时间、Tracker 来源。

#### BL-05 · 每条规则达到 G3 所需的最小几何变体数量

- [R21] NIST covering-array 方法支持按离散 factor/t-way interaction 构造较小但可量化覆盖的回归集；不提供海事 MPC 固定最小样本数。
- [R19][R20] 上游 PSB benchmark 每 stratum 100 episode（BL-03 已确认无缩减集）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 canonical G3 set 按 t=2（pairwise）覆盖 4 类双船规则 × 关键 factor（initial bearing、speed ratio、CPA bin、 Tracker）；具体数量转 BL-80 裁决（A 档后台调研中）。
- 证据边界：当前可冻结"采用 covering-array 方法 + 声明为本项目新建 regression set"；具体 t-way strength 与数量 UNKNOWN，待 BL-80。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-10 · Custom MPC 首次交付形式和运行环境

- [R3][R9] 当前 `ICOLAV` 是稳定边界；`COLAVBuilder.construct_colav()` 从 `Config` 构建 `VOWrapper`/`SBMPCWrapper`。
- [R11] `custom_mpc_adapter.py` 是 guidance 层 `IGuidance`，非 `ICOLAV`；含硬编码 `sys.path.insert` 与静默 fallback（ALT-04 已弃用）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：Custom MPC 首次交付为 `CustomMPCAdapter(ICOLAV)` 薄适配器，Adapter 负责验证/转换，不实现算法策略；in-process 优先（BL-95/96 后置裁决 Worker）；algorithm_config 经 `RunSpec.algorithm_config` 注入。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-11 · 扩展 ICOLAV.plan 参数还是引入 typed request DTO

- [R3] 当前 `ICOLAV.plan(t, waypoints, speed_plan, ownship_state, do_list, enc, goal_state, w, **kwargs)` 已有 9 个位置参数 + kwargs；继续扩展会使签名脆弱。
- [R9] `RunSpec`、`PlanDiagnostics` 已是 typed dataclass 模式。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：Adapter 内构造 typed `PlannerInput` DTO（含 ownship/track/enc/reference/seed/identity/time_validity），保持外部 `ICOLAV.plan()` 签名兼容；Adapter 验证结构/语义，solver 判断优化可行性；无效输入显式 `INVALID_INPUT`。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-12 · 坐标、单位、时间有效性和 Track 数据质量的 Adapter/solver 验证边界

- [R3] 当前 `do_list` 裸元组无坐标系/单位/时间戳字段。
- [R9] `RunSpec` 已有 schema_version。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：Adapter 验证坐标系（ENU）、单位（SI）、Track age（BL-14）、covariance PSD（BL-15）、finite/shape；solver 只判断优化可行性。技术规约（坐标系/单位/符号/时序）在 Step6 [TS] 锁定。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-13 · Custom MPC 配置 schema、版本和参数身份记录方式

- [R9] `RunSpec.algorithm_config: dict` 已存在但无 schema/version/hash。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：`AlgorithmDescriptor`（BL-22）携带版本化、可哈希 config；manifest 保存冻结副本（content hash）；动态变化进 PlannerTrace。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-14 · Track 最大允许 age；过期后拒绝还是标记降级

- [R30][R31] 当前 Radar 用 NaN 同时表示未扫描/超距/漏检（BL-43 已确认三态扫描契约）；VIM Adapter 无有效量测不调底层 step。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：Track age 阈值作 profile 参数（默认值待裁决，参考 Radar scan 周期整数倍）；超龄 `degraded` 标志，不自动拒绝（God/KF profile 差异）；Adapter 透传 age，solver 决定是否用。
- 证据边界：可冻结"profile 化 + degraded 标志"；具体秒数 UNKNOWN。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-15 · covariance 坐标系、状态顺序、PSD 容差及缺失政策

- [R3] 当前 `do_list` covariance 是 `np.ndarray`，无坐标系/状态顺序声明。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：covariance 坐标系 = NED/ENU（与 ownship_state 一致，Step6 [TS] 锁定）；状态顺序 `[x, y, Vx, Vy]`（与 do_list state 一致）；Adapter 检查对称 + 半正定（特征值 ≥ -ε，ε 待裁决）；缺失 covariance → `INVALID_INPUT`（不静默补单位阵）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-16 · MPC 接收完整 ENC 对象还是裁剪后的可序列化 hazard geometry

- [R3] 当前 `ICOLAV.plan(enc: senc.ENC)` 接收完整 ENC 对象（含 Shapely geometry）。
- [R35] ENC 加载慢（GDAL/SeaCharts），且 native Worker 跨进程序列化大 geometry 昂贵（BL-98 后置）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：in-process 传完整 ENC；subprocess Worker 传裁剪后的可序列化 hazard geometry（footprint-relevant union + bbox + SHA）；Adapter 声明所需 hazard layers（BL-69 四类分离）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-17 · 目标船 length/width 缺失或不可信时的处理政策

- [R3] 当前 `do_list` 含 `(length, width)` 但无来源/置信度。
- [R28] FCB45 目标船参数本身带 HAZID-UNVERIFIED。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：缺失 → `INVALID_INPUT`（不静默补默认值）；不可信（带 UNVERIFIED 标记）→ `degraded` 标志，Adapter 透传，solver 决定；fallback footprint（BL-65 五边形）须显式标记。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-18 · horizon 第 0 列表示当前状态还是下一控制时刻

- [R3] 当前 `ICOLAV.plan()` 返回 `9xN`，VOWrapper 把 `trace_plan[0:2,0] = ownship_state[0:2]`（首列覆写为当前状态）；SBMPCWrapper 的 `debug["prediction"]` 首列语义未显式声明。
- [R29] trajectory 记录的 state 是区间起点，reference 是本区间新指令。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：horizon 第 0 列 = solve-time 当前状态（`t_solve`），后续列 = `t_solve + k*horizon_dt`；`selected_command`（首列的执行指令）单独字段；hold 步不重置 horizon 原点（BL-28）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-19 · solver 状态维度不是 9 时，加速度/缺失状态的映射方式

- [R3] `9xN` = `[x, y, psi, u, v, r, x_ddot, y_ddot, psi_dot]`（pose + vel + acc）。
- [R32] SB-MPC predictor 是简化模型（`v=r=0`），不产出完整 9 维。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：Adapter 提供 `StateMapping`（版本化），把 native state 映射到 9 维；缺失维度填 0 并在 `algorithm_details` 标 `estimated=false`；不得静默补非零值。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-20 · 输出轨迹连续性、物理一致性和首点误差容差

- [R3] `validate_plan()` 已检查 `shape(9,N>=1)` + finite。
- [R29] 当前无连续性/物理一致性检查。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：Adapter 增加连续性检查（相邻列位移 ≤ `(|v|max + |w|max·r_max)·horizon_dt` 上界，BL-66 motion bound）；首点位置误差 ≤ footprint tolerance（BL-65）；违规 → `NUMERICAL_FAILURE`。具体数值容差后置。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-21 · selected_control 表示参考指令还是原始 MPC 控制量

- [R3] VOWrapper `selected_command = {course_rad, speed_mps}`；SBMPCWrapper 含 `course_offset_rad, speed_scale`。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：`selected_command` = 控制器兼容参考指令（course/speed 或 force/torque，由 `AlgorithmDescriptor.control_form` 声明）；原始 MPC 控制量（如 SQP `u`）进 `algorithm_details`；两者都绑定同一 `solve_id`。
- 状态：证据已登记，未标闭环，等待用户确认。

#### 本批用户确认门

- 待用户分别确认 BL-05, BL-10..21 的证据是否回答原问题。
- 建议确认口径（统一 DESIGN_CANDIDATE，数值后置）：
  - BL-05：covering-array t=2 方法 + 声明本项目 regression set；具体数量待 BL-80。
  - BL-10：Custom MPC 首次交付为 `CustomMPCAdapter(ICOLAV)` 薄适配器；in-process 优先。
  - BL-11：Adapter 内 typed `PlannerInput` DTO；保持 `ICOLAV.plan()` 签名兼容。
  - BL-12：Adapter 验证坐标/单位/时间/Track 质量；solver 判断优化可行性；技术规约 Step6 锁定。
  - BL-13：`AlgorithmDescriptor` 版本化可哈希 config；manifest 冻结副本。
  - BL-14：Track age profile 化 + degraded 标志；具体秒数后置。
  - BL-15：covariance 坐标系/状态顺序与 ownship 一致；PSD 检查；缺失 → INVALID_INPUT。
  - BL-16：in-process 传完整 ENC；Worker 传裁剪 hazard geometry + SHA。
  - BL-17：缺失 → INVALID_INPUT；不可信 → degraded 标志；fallback footprint 显式标记。
  - BL-18：horizon 第 0 列 = solve-time 当前状态；selected_command 单独字段。
  - BL-19：`StateMapping` 版本化映射；缺失维度填 0 并标 `estimated=false`。
  - BL-20：连续性检查（motion bound 上界）；首点误差 ≤ footprint tolerance；具体数值后置。
  - BL-21：selected_command = 控制器兼容参考；原始控制量进 algorithm_details；同 solve_id。
- 未确认前不改盲区为"已闭环"，不进入 Step4，不实施代码。

### Step3 · 第九批证据用户确认（B 档第一批） [2026-07-28]

- 用户批量确认本批全部证据。
- BL-05 边界闭环：采用 covering-array t=2 方法 + 声明为本项目新建 regression set；具体数量待 BL-80。
- BL-10 闭环：Custom MPC 首次交付为 `CustomMPCAdapter(ICOLAV)` 薄适配器；in-process 优先；Worker 后置。
- BL-11 闭环：Adapter 内 typed `PlannerInput` DTO；保持 `ICOLAV.plan()` 签名兼容。
- BL-12 边界闭环：Adapter 验证坐标/单位/时间/Track 质量；solver 判断优化可行性；技术规约 Step6 锁定。
- BL-13 闭环：`AlgorithmDescriptor` 版本化可哈希 config；manifest 冻结副本。
- BL-14 边界闭环：Track age profile 化 + degraded 标志；具体秒数后置。
- BL-15 闭环：covariance 坐标系/状态顺序与 ownship 一致；PSD 检查；缺失 → INVALID_INPUT。
- BL-16 闭环：in-process 传完整 ENC；Worker 传裁剪 hazard geometry + SHA。
- BL-17 闭环：缺失 → INVALID_INPUT；不可信 → degraded；fallback footprint 显式标记。
- BL-18 闭环：horizon 第 0 列 = solve-time 当前状态；selected_command 单独字段。
- BL-19 闭环：`StateMapping` 版本化映射；缺失维度填 0 标 `estimated=false`。
- BL-20 边界闭环：连续性检查（motion bound 上界）；首点误差 ≤ footprint tolerance；具体数值后置。
- BL-21 闭环：selected_command = 控制器兼容参考；原始控制量进 algorithm_details；同 solve_id。
- Step3 尚未完成；不进入 Step4。

### Step3 · 第十批深度调研（B 档第二批）：TD-01 Custom MPC 插件契约 — DP-11/12/13/14 接口盲区批量裁决 [2026-07-28]

#### 取证摘要

- 本批为路径 1 加速的 B 档第二批：TD-01（Custom MPC 插件契约）的 DP-11/12/13/14 接口设计盲区，共 17 项（BL-22..38）。
- 与第九批同，本批盲区多为接口设计裁决（字段名/schema/容差/时间锚点/失败语义/诊断字段），不依赖外部 primary source，主要证据来自 PROJECT_FACT（当前 `PlanStatus`/`PlanDiagnostics`/`PlannerTrace`/`SeedBundle`/`RunSpec` 代码）+ Step2 已确认的 grilling 结论（DP-11..14）。
- 关键脚手架事实：
  - `PlanStatus`（StrEnum）已有 `SUCCESS/TIMEOUT_FEASIBLE/INFEASIBLE/NUMERICAL_FAILURE/INVALID_INPUT/DEPENDENCY_UNAVAILABLE` 六态（DP-13 BL-31..34 基础已备）。
  - `PlannerTrace` 已有 `schema_version="1.0"`、`solve_id`、`solver_executed`、`predicted_trajectory`、`horizon_dt_s`、`selected_command`、`target_predictions`、`constraints`、`algorithm_details`（DP-14 BL-35..38 字段骨架已备）。
  - `PlanDiagnostics` 已有 `status/elapsed_ms/iterations/feasible/objective/reason/requested_algorithm/executed_algorithm/fallback_used/details`。
  - `SeedBundle` 已派生 `scenario/sensor/tracker/algorithm` 四流（BL-58 已闭环）；`RunSpec.strict_no_fallback` 已存在（DP-13 grilling 基础）。

#### BL-22 · `AlgorithmDescriptor` 强制字段与允许 `not_applicable` 字段

- [R9] 当前无 `AlgorithmDescriptor`；`RunSpec.algorithm_config: dict` 无 schema。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：强制字段 = `algorithm_id/version/control_form/state_layout/predictor_model/horizon_dt/horizon_steps/objective_terms/constraint_terms/solver/seed_policy/execution_profile`；允许 `not_applicable` 字段 = `iterations_semantics/objective_normalization/failure_modes`（声明即可，不强制值）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-23 · 外部二进制/服务的代码 SHA、build 和依赖身份获取方式

- [R40] `RunManifest` 已记录 `code_commit/code_dirty/python_version/external_modules`（BL-60 runtime fingerprint 基础已备）。
- [R43][R44] PSB/RLMPC native 二进制身份需 repo SHA + module/binary SHA + solver/library version + compiler/CMake/build flags + codegen/config hash。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：`AlgorithmDescriptor.build_identity` 携带上述字段；Adapter 探测 + manifest 冻结；缺失字段标 `UNKNOWN` 不得伪造。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-24 · 自适应权重、动态 horizon 和在线模式切换的记录方式

- [R9] 当前 `algorithm_config: dict` 无版本/快照；`PlannerTrace.algorithm_details` 可存动态值。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：静态配置进 `AlgorithmDescriptor`（冻结）；每步动态值（权重/horizon/mode）进 `PlannerTrace.algorithm_details`（绑定 `solve_id`）；manifest 不含动态值。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-25 · 目标函数和约束名称是否需要公共分类词表

- [R2][R48] 论文用 `S_safety/S_r/S_theta/S8/S13..S17`；当前重建用自由命名。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：公共分类词表（如 `objective: {tracking_error, control_effort, collision_risk, colreg_compliance}`；`constraint: {safety_domain, enc_clearance, control_envelope, colreg_role}`）；Adapter 声明用到的公共 + 算法专项项；不同算法的 objective 不横向比较（BL-77）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-26 · 首次求解发生在 `t=0` 还是首个 `dt_sim` 后

- [R29] 当前 VOWrapper 首步 `if not self._initialized: self._t_prev = t`，SBMPCWrapper `if not self._initialized or t < 0.0001`。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：首次 solve 发生在 `t=0`（仿真起点），用初始 ownship_state + 初始 reference；`solve_id=1` 在首步；hold 步 `solver_executed=false`。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-27 · solve period/deadline 由算法声明，还是允许 RunSpec 覆盖

- [R3] SBMPCWrapper 硬编码 `t - self._t_run_sbmpc_last >= 5.0`（求解周期）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：`AlgorithmDescriptor.solve_period_s` 声明默认；`RunSpec` 可覆盖（声明覆盖）；deadline（BL-79）由 profile + normalize budget 裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-28 · 非求解步对上一 horizon 采用采样推进、插值还是固定第一指令

- [R29] SBMPCWrapper hold 步保留 `self._speed_os_best/course_os_best`，但 `sim_time` 被改写为当前步。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：hold 步保留同一 horizon（原点 `t_solve` 不变），执行指令从该 horizon 按 `t_now - t_solve` 采样（不重新 solve）；`solver_executed=false`；不得把 hold 帧当新预测起点。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-29 · warm start 与随机求解器的 reset/replay 保证范围

- [R44] RLMPC warm start 跨 run 不可复用（reset 后状态丢失）。
- [R43] PSB CPE seed 需 `set_seed()`（BL-57 tolerance-only）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：reset 清空 warm start；replay 重新冷启动；声明 warm-started 的 Adapter 须通过 reset probe（BL-100）；无 seed API 的 native 不获 exact 资格。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-30 · 离线快速仿真是否也强制实时 deadline

- [R34] 当前无 deadline 强制。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：离线快速仿真可选关闭硬 deadline（`RunSpec.deadline_mode = OFF`），但正式资格 run 必须开启；关闭时 run 标 `diagnostic_only` 不进 G3。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-31 · `TIMEOUT_FEASIBLE` 超过 deadline 后是否仍允许执行

- [R9] `PlanStatus.TIMEOUT_FEASIBLE` 已存在。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：`TIMEOUT_FEASIBLE` 可执行当前可行解（非 hold），但计入 deadline 失败统计；连续 `TIMEOUT_FEASIBLE` 上限（BL-33）后判 run 失败；G3 要求零 deadline 失败（BL-82）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-32 · Web 调试模式失败后终止，还是冻结/hold 以便观察

- [R31] Web 是只读观察/控制端（DP-31 grilling）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：正式 run fail-stop；Web 调试模式可 `hold_on_failure`（冻结显示，不推进），但该 run 标 `diagnostic_only` 不进正式结果。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-33 · 连续可行超时多少次后判定整个 run 失败

- [R9] 当前无连续超时计数。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：连续 `TIMEOUT_FEASIBLE` 阈值作 profile 参数（默认值待裁决，参考 solve_period 整数倍）；超阈值后 run `FAILED`，`primary_reason=REALTIME`。
- 证据边界：可冻结"profile 化 + run FAILED"；具体次数 UNKNOWN。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-34 · `INVALID_INPUT` 归因于场景、Adapter 或算法的规则

- [R9] `PlanStatus.INVALID_INPUT` 已存在但无归因字段。
- [R34] 当前异常分类粗糙（BL-50 已确认多标签归因）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：`INVALID_INPUT` 归因 = `SCENARIO`（坐标/几何/船模无效）/ `ADAPTER`（DTO 转换/单位/坐标系错误）/ `ALGORITHM`（solver 拒绝声明 envelope 内输入）；Adapter 标 `invalid_source`，Evaluator 计入对应分母。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-35 · 公共必需字段与 MPC 专项必需字段的边界

- [R9] `PlannerTrace` 已有公共字段（`algorithm_id/solve_id/sim_time/solver_executed/status/predicted_trajectory/horizon_dt_s/selected_command`）；`algorithm_details` 存专项。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：公共必需 = `algorithm_id/solve_id/sim_time/solver_executed/status/elapsed_ms/predicted_trajectory/horizon_dt_s/selected_command`；MPC 专项必需 = `objective/iterations/feasible/constraints`（进公共字段，非 algorithm_details）；算法特定诊断进 `algorithm_details`。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-36 · cost/constraint 公共分类词表与最小裕度表示

- [R2] 论文 cost/constraint 有命名；当前重建用自由命名。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：与 BL-25 共享分类词表；最小裕度（如 safety domain margin、enc clearance margin）以 SI 单位输出，进 `constraints` 字段；不同算法的 cost 不横向比较（BL-77）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-37 · 多模态目标预测、概率和 covariance 的 trace schema

- [R9] `target_predictions: list[dict]` 已存在但无 schema。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：每 target = `{target_id, mode_id, probability, predicted_trajectory[Nx9], covariance[Nx4x4], source}`；缺概率时单模态 `probability=1.0`；多模态概率和 = 1（Adapter 验证）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-38 · 长时域、多目标 trace 的体积、压缩和保留策略

- [R29] trajectory.parquet 为省体积已删完整 horizon；events.jsonl 保留。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：trace 分层——events.jsonl 增量写完整 solve（含 horizon）；trajectory.parquet 每步 state/reference/selected_command；大 horizon（>1000 步）或多目标（>10）启用 per-solve 单独文件 + 引用；schema_version 标注。
- 状态：证据已登记，未标闭环，等待用户确认。

#### 本批用户确认门

- 待用户分别确认 BL-22..38 的证据是否回答原问题。
- 建议确认口径（统一 DESIGN_CANDIDATE，数值后置）：
  - BL-22：AlgorithmDescriptor 强制字段 + 允许 not_applicable 字段。
  - BL-23：build_identity 携带 SHA/binary/solver/build flags；缺失标 UNKNOWN。
  - BL-24：静态配置进 Descriptor，动态值进 algorithm_details 绑 solve_id。
  - BL-25：公共 cost/constraint 分类词表；不横向比较。
  - BL-26：首次 solve 在 t=0；solve_id=1 首步。
  - BL-27：solve_period 算法声明 + RunSpec 可覆盖；deadline 后置。
  - BL-28：hold 步保留 horizon 原点，按 t_now 采样；不重新 solve。
  - BL-29：reset 清 warm start；无 seed API 不获 exact。
  - BL-30：离线可关 deadline，标 diagnostic_only 不进 G3。
  - BL-31：TIMEOUT_FEASIBLE 可执行但计 deadline 失败；G3 零 deadline 失败。
  - BL-32：Web 调试可 hold_on_failure，标 diagnostic_only。
  - BL-33：连续 TIMEOUT 阈值 profile 化；超阈 run FAILED。
  - BL-34：INVALID_INPUT 归因 SCENARIO/ADAPTER/ALGORITHM。
  - BL-35：公共必需字段 + MPC 专项必需字段分边界。
  - BL-36：与 BL-25 共享词表；最小裕度 SI 单位进 constraints。
  - BL-37：target 多模态 schema（mode/prob/trajectory/cov/source）。
  - BL-38：trace 分层（events 增量 + trajectory 每步 + 大 horizon 单独文件）。
- 未确认前不改盲区为"已闭环"，不进入 Step4，不实施代码。

### Step3 · 第十批证据用户确认（B 档第二批） [2026-07-28]

- 用户批量确认本批全部证据。
- BL-22 闭环：AlgorithmDescriptor 强制 12 字段 + 允许 not_applicable 字段。
- BL-23 闭环：build_identity 携带 SHA/binary/solver/build flags；缺失标 UNKNOWN 不伪造。
- BL-24 闭环：静态配置进 Descriptor，动态值进 algorithm_details 绑 solve_id。
- BL-25 闭环：公共 cost/constraint 分类词表；不横向比较。
- BL-26 闭环：首次 solve 在 t=0；solve_id=1 首步。
- BL-27 边界闭环：solve_period 算法声明 + RunSpec 可覆盖；deadline profile 后置。
- BL-28 闭环：hold 步保留 horizon 原点，按 t_now 采样；不重新 solve。
- BL-29 闭环：reset 清 warm start；无 seed API 不获 exact。
- BL-30 闭环：离线可关 deadline，标 diagnostic_only 不进 G3。
- BL-31 闭环：TIMEOUT_FEASIBLE 可执行但计 deadline 失败；G3 零 deadline 失败。
- BL-32 闭环：Web 调试可 hold_on_failure，标 diagnostic_only。
- BL-33 边界闭环：连续 TIMEOUT 阈值 profile 化；超阈 run FAILED；具体次数后置。
- BL-34 闭环：INVALID_INPUT 归因 SCENARIO/ADAPTER/ALGORITHM。
- BL-35 闭环：公共必需字段 + MPC 专项必需字段分边界。
- BL-36 闭环：与 BL-25 共享词表；最小裕度 SI 单位进 constraints。
- BL-37 闭环：target 多模态 schema（mode/prob/trajectory/cov/source）。
- BL-38 闭环：trace 分层（events 增量 + trajectory 每步 + 大 horizon 单独文件）。
- Step3 尚未完成；不进入 Step4。

### Step3 · 第十一批深度调研（C 档）：Worker 隔离、证据包与 Web schema 工程盲区批量裁决 [2026-07-28]

#### 取证摘要

- 本批为路径 1 加速的 C 档：DP-26（证据包 BL-90..94）/ DP-27（Worker 隔离 BL-95..99）/ DP-28（runtime 身份 BL-100..103）/ DP-29（Worker 通信 BL-104..108）/ DP-31（Web 只读 BL-114..118），共 24 项。
- 与 B 档同，本批盲区多为工程/schema 裁决，主要证据来自 PROJECT_FACT（`RunManifest`/`EvidenceWriter`/`ExperimentRunner`/`persistence.py` 代码）+ Step2 已确认 grilling（DP-26/27/28/29/31）。
- 关键脚手架事实：
  - `RunManifest` 已有 16+ identity 字段、`schema_version="1.0"`、`replay_verified`、`fallback_used`、`failure_reason/status`、`capability_profile_id`、`scenario_provenance`。
  - `EvidenceWriter` 已写 manifest/episode/events.jsonl/trajectory.parquet/evaluation/report 六件套；`write_failure_report` 处理失败 run；persistence 用 `subprocess.run` 隔离 pandas。
  - `ExperimentRunner` 已有 `prepare/run/replay/persist_failure/_enforce_no_fallback`。
  - 无 Worker（subprocess/container）实现；无 WebSocket 实现；无 schema 演进/防篡改机制。

#### DP-26 · 证据包 schema（BL-90..94）

##### BL-90 · trajectory/events 字段和列级 schema
- [R10] 当前 events.jsonl 写 PlannerTrace.to_dict()；trajectory.parquet 写逐帧 dict。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：trajectory 列级 schema = `{sim_time, solve_id, state[9], reference[9], applied_control, solver_executed, sat_flags}`；events schema = `{schema_version, solve_id, sim_time, solver_executed, status, horizon[9xN], horizon_dt, selected_command, target_predictions, constraints, algorithm_details}`；列级 schema_version 标注。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-91 · native crash 下增量写入、flush 和原子封存
- [R10] 当前 `write_events` 批量写；native crash（SIGABRT）会丢失未 flush 数据。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：events.jsonl 改 append 模式（每 solve 后 flush + fsync）；manifest/evaluation/report 用 `.tmp` + atomic rename；crash 后保留已写部分 + `partial` 标志。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-92 · 大型 horizon/目标预测拆文件还是保留 JSONL
- [R29] trajectory.parquet 为省体积已删完整 horizon。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：events.jsonl 默认内联 horizon（< 阈值）；超阈值（如 >1000 步 或 >10 目标）拆 per-solve `{run_id}/solves/{solve_id}.json` + events 引用；阈值 profile 化。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-93 · 内容 hash、签名和防篡改级别
- [R40] 当前 `trajectory_hash` 是文件 SHA-256（BL-56 已确认混合数值+编码）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 内容 hash（canonical JSON SHA-256）+ manifest 签发（不加密签名，本地单用户）；防篡改级别 = `tamper_evident`（hash 不匹配标 INVALID），非 `tamper_proof`。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-94 · legacy pickle 最小兼容范围
- [R10] 当前无 pickle；上游历史可能用 pickle。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 不支持 pickle 读写；只读 legacy pickle 仅用于一次性迁移（SC-10），带 `legacy_pickle` 标志，不进正式证据链。
- 状态：证据已登记，未标闭环，等待用户确认。

#### DP-27 · Worker 隔离（BL-95..99）

##### BL-95 · subprocess 与 container 选择规则
- [R11] 当前无 Worker；`custom_mpc_adapter` 全 in-process。
- [R43][R44] PSB native abort / RLMPC 依赖冲突需进程隔离。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 优先 subprocess（`multiprocessing` 或 `subprocess.Popen`）；container 仅用于无法共存的依赖 profile（如 RLMPC acados vs PSB Eigen）；选择规则由 `AlgorithmDescriptor.execution_profile` + Registry 探测决定。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-96 · 每 run 新建 Worker 还是 session 内持久
- [R10] 当前 in-process 每 episode reset。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 每 run 新建 Worker（冷启动，匹配 BL-29 reset 语义）；持久 Worker 后置（需 BL-103 泄漏检测通过）。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-97 · Worker startup/reset 后状态隔离和可重放性
- [R40] replay 要求独立 Worker + 独立 seed tree（BL-57/58 已确认）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：Worker startup/reset 后清空所有内部状态（warm start、cache、RNG）；replay 用新 Worker + 同 seed + 同 runtime fingerprint；reset probe（BL-100）验证零残留。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-98 · ENC geometry 和大 horizon IPC 性能
- [R35] ENC 加载慢；大 geometry 跨进程序列化昂贵。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：in-process 传完整 ENC（BL-16）；subprocess Worker 传裁剪 hazard geometry（BL-69 四类 + footprint-relevant union）；大 horizon 用共享内存或 memoryview；序列化格式 = MessagePack/Arrow（非 pickle）。
- 证据边界：具体 IPC 格式与共享内存方案待实现期裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-99 · 本地单用户 Worker 最小安全限制
- [R11] 本地单用户（DP-31 grilling 已确认）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 最小安全 = Worker 无网络访问、无文件系统写（除指定 output_dir）、CPU/内存上限（resource.setrlimit）；不做鉴权（BL-117）；container profile 加 seccomp/AppArmor。
- 状态：证据已登记，未标闭环，等待用户确认。

#### DP-28 · runtime 身份（BL-100..103）

##### BL-100 · in-process 准入所需 crash/timeout/reset 测试
- [R43][R44] native abort 不能由 Python try/except 捕获。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：in-process 准入需通过：①crash probe（注入异常，确认不崩主进程）；②timeout probe（确认可中断）；③reset probe（BL-97，确认零状态残留）；④replay probe（同 seed 零漂移，BL-57）。四 probe 全过才 in-process，否则 subprocess。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-101 · Python/native 依赖 lock 和 build identity 采集方法
- [R40] `RunManifest.dependencies` 已存在但无 lock 文件 hash。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：lockfile（`uv.lock`/`requirements.txt`）hash 进 manifest；native 依赖（CMake/build flags/binary SHA）进 `AlgorithmDescriptor.build_identity`（BL-23）；缺失标 UNKNOWN。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-102 · container image digest 与本地源码身份关联
- [R11] container 仅用于无法共存 profile。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：container profile 记录 image digest + 本地源码 commit + mount 路径；digest 与 commit 关联进 manifest；无 digest 则标 `unreproducible`。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-103 · 持久 Worker 跨 episode 状态泄漏检测
- [R10] 当前 in-process。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：持久 Worker 后置；启用前须通过泄漏 probe（同 episode 两次 run，比对 horizon/state/RNG 序列零差异）；V1 不启用持久 Worker（BL-96 每 run 新建）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### DP-29 · Worker 通信（BL-104..108）

##### BL-104 · IPC framing/encoding 选择及大数组传输
- [R10] 当前无 IPC。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 subprocess 用 stdin/stdout JSON Lines（每行一帧：`{request_id, type, payload}`）；大数组（horizon/ENC）用 base64 Arrow IPC 或共享内存；stderr 留日志（BL-107）；不 pickle。
- 证据边界：具体编码待实现期裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-105 · deadline、grace period、terminate/kill 时序
- [R9] `PlanStatus.TIMEOUT_FEASIBLE` 已存在。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：parent 持有 hard deadline；超时先 `SIGTERM`（grace period 内收集部分响应），再 `SIGKILL`；crash/timeout 使当前 run 失败（BL-31）；Worker 仅为下一 run 重建（BL-96）。
- 证据边界：grace period 数值待裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-106 · Worker 在 run 间重建与健康检查策略
- [R10] 当前无 Worker。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 每 run 新建（BL-96）；健康检查 = startup probe（`health` 请求）；run 间不持久（BL-103 后置）。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-107 · stderr 保留大小、敏感信息清理和报告方式
- [R10] 当前无 stderr 收集。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：stderr 截断保留（上限如 1MB）进 `evidence/stderr.log`；清理明显敏感信息（路径/密钥占位符，本地单用户风险低）；failure_reason 引用 stderr 尾部。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-108 · request 去重和有状态 plan 幂等边界
- [R9] `solve_id` 已存在。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：每 plan 请求唯一 `request_id` + `solve_id`；plan 不自动重试（BL-57）；相同 `request_id` 重复 = 客户端错误（不重新 solve）；有状态 plan 的幂等 = 同 request_id 返回缓存结果（仅未超时时）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### DP-31 · Web 只读边界（BL-114..118）

##### BL-114 · WebSocket schema 版本兼容和字段演进规则
- [R31] Web 是只读投影（DP-31 grilling）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：WebSocket 消息带 `schema_version`；字段演进 = additive-only（新增字段不破坏旧客户端）；删除/重命名字段需 bump major version + 兼容窗口。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-115 · 实时推送频率、背压和慢客户端政策
- [R31] 当前无 WebSocket 实现。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：推送频率 = 仿真步降采样（如每 N 步或每 100ms）；背压 = 慢客户端丢弃中间帧（保留最新）；断连不影响 run（DP-31）；客户端重连用 `seq` 追赶。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-116 · 当前 horizon/ENC/目标预测的大数据传输策略
- [R31] 当前无大数据传输。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：Web 不发完整 raw horizon/ENC（DP-31 grilling 已确认）；降采样投影（如 horizon 前 20 点、ENC bbox outline）；大数据走 REST artifact 下载。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-117 · 本地单用户是否完全不做鉴权
- [R11] 本地单用户。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：V1 本地单用户不做鉴权；绑定 `127.0.0.1`（不暴露公网）；若需远程访问，后置加 token + TLS。
- 状态：证据已登记，未标闭环，等待用户确认。

##### BL-118 · live state 与持久化 artifact 的 seq/hash 对齐
- [R40] manifest 有 hash；live state 无 seq。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：live state 带单调 `seq`；Web 消息带 `seq` + 当前 manifest hash；客户端可校验 live seq ≤ artifact seq；run 结束后 artifact 为权威，live 不再更新。
- 状态：证据已登记，未标闭环，等待用户确认。

#### 本批用户确认门

- 待用户批量确认 BL-90..94, BL-95..99, BL-100..103, BL-104..108, BL-114..118（共 24 项）的证据是否回答原问题。
- 建议确认口径（统一 DESIGN_CANDIDATE，数值后置）：
  - BL-90：trajectory/events 列级 schema + schema_version。
  - BL-91：events append + fsync；atomic rename；crash 保留 partial。
  - BL-92：大 horizon 拆 per-solve 文件 + 引用；阈值 profile 化。
  - BL-93：内容 hash + tamper_evident（非 tamper_proof）。
  - BL-94：V1 不支持 pickle；legacy 仅一次性迁移。
  - BL-95：subprocess 优先；container 仅无法共存 profile。
  - BL-96：V1 每 run 新建 Worker；持久后置。
  - BL-97：Worker reset 清空所有状态；replay 新 Worker + 同 seed。
  - BL-98：in-process 完整 ENC；Worker 裁剪 geometry；MessagePack/Arrow。
  - BL-99：无网络/无文件写/CPU-内存上限；不做鉴权。
  - BL-100：in-process 准入需 crash/timeout/reset/replay 四 probe。
  - BL-101：lockfile hash + native build_identity 进 manifest。
  - BL-102：container digest + commit 关联；无 digest 标 unreproducible。
  - BL-103：持久 Worker 后置；启用前须泄漏 probe。
  - BL-104：JSON Lines framing；大数组 Arrow/shared memory；不 pickle。
  - BL-105：SIGTERM grace → SIGKILL；crash/timeout run 失败。
  - BL-106：V1 每 run 新建；startup health probe。
  - BL-107：stderr 截断保留；清理敏感占位符。
  - BL-108：唯一 request_id + solve_id；plan 不重试；幂等返回缓存。
  - BL-114：schema_version + additive-only 演进。
  - BL-115：降采样推送；慢客户端丢帧；断连不影响 run。
  - BL-116：不发 raw horizon/ENC；REST artifact 下载。
  - BL-117：本地单用户不做鉴权；绑 127.0.0.1。
  - BL-118：live seq + manifest hash；artifact 为权威。
- 未确认前不改盲区为"已闭环"，不进入 Step4，不实施代码。

### Step3 · 第十二批深度调研（A 档）：DP-24 G2/G3/G4 资格门、组合兼容性与自动晋级 [2026-07-28]

#### 取证摘要

- 本批为 A 档深度调研第二组，对应 DP-24 资格门体系的 BL-80..84。
- **NLM 笔记本本批未可用**：`notebooklm login` token 过期，`ask` 调用返回 "Authentication expired"，需交互式浏览器 OAuth，subagent 无法执行。已按 fallback 规则全部走 primary source + 项目自身代码/设计文档。
- 关键脚手架事实（PROJECT_FACT）：
  - G0..G4 定义已固定在 `Design/Algorithm-Capability-Matrix.md` §1（G3=相对 nominal 出现符合算法职责的可观察动作和诊断；G4=固定场景矩阵、多 seed、统一 Evaluator 和统计通过）。
  - `capability_profile_id` 已是 4-tuple `{rule}:{scenario}:{algorithm}:{tracker}`（`runner.py:141`）。
  - `PlanStatus` 已有 `SUCCESS/TIMEOUT_FEASIBLE/INFEASIBLE/NUMERICAL_FAILURE/INVALID_INPUT/DEPENDENCY_UNAVAILABLE`（`diagnostics.py:12`）。
  - 当前 G3 证据为**每组合恰好 1 episode**（seed=0，episode_index=0，Rule 14 head_on×God）。
  - `BatchRunner.default_specs` 默认 `seeds=range(30)` + 计算 95% CI（`batch.py:165-171`，`mean ± 1.96·std/√n`）。
  - `STANDARD_SCENARIOS` = head_on/crossing_give_way/crossing_stand_on/overtaking/overtaken（5 strata）。
  - `RunManifest` 已 hash `code_commit/dependencies/spec_hash/scenario_hash/episode_hash/trajectory_hash/scenario_provenance/evaluator_id`；**缺独立 `enc_hash`**（ENC 内容仅经 path 进 scenario_hash）。

#### BL-80 · G3 canonical set 每条规则的 episode 数量

- [R21] NIST covering-array 方法：`CA(N; t, k, v)` 需最小 N 使每 t-way 组合至少出现一次。对 ~10 参数×4 值：t=2 需 **≈16-20** 测试用例（下界 v²=16）；t=3 需 **≈64-88**（下界 v³=64）。t=2 是回归级覆盖的常规最小；t=3 捕获 t=2 漏的交互故障但 set size ~4×。
- 无海事源强制最小 episode 数。Hagen 2023/Tengesdal 2023 定义评价**方法**，非样本量阈值。BL-03 已确认上游 PSB benchmark 每 stratum 100 是 benchmark 选择，非标准要求。
- 当前 G3 证据为 1 episode/组合（seed 0），严格低于任何可辩护的回归阈值。
- 项目自身 `BatchRunner` 已定 `range(30)` + 95% CI；canonical G3 set 若 < 30 与项目既有 batch 统计不一致。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 不选单一全局"N per rule"。canonical G3 set = 固定 covering array over V1 参数空间 + 每行多 seed。
  - 具体：**canonical G3 = t=2 covering array（≥16 代表性 encounter 参数化/rule family）× 3 seeds × 所有 G3-eligible (algorithm, tracker) cells**，cell 的 G3 要求**所有 seed 零硬门失败**。
  - G4 保留全 `range(30)` + 95% CI（`BatchRunner` 既有机制）。
- 证据边界：可冻结"covering-array + 多 seed + 零硬门"；具体 t-way strength（t=2 vs t=3）与 seed 数（3 vs 5）待 DP-24 裁决，标 UNKNOWN。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-81 · 证据失效的字段和兼容变更规则

- [R40] `RunManifest` 已记录 SHA-256/identity 的字段：`code_commit/code_dirty`、`dependencies`、`spec_hash`、`simulation_config_hash`、`scenario_hash`、`episode_hash`、`trajectory_hash`、`scenario_provenance`、`evaluator_id`、`capability_profile_id`、requested/executed algorithm&tracker、readiness grades。
- [R35] **ENC 内容未单独 hash**——仅经 path 进 `scenario_hash`，是真实 gap。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - manifest 增 `enc_hash`（ENC 内容 SHA-256）。
  - 增显式 `capability_dependencies` 聚合：`[code_commit, dependencies, scenario_hash, enc_hash, evaluator_id, tracker_id+config, plant_id+params, runtime_fingerprint]`。
  - 失效规则：prior G3 pass 在 `capability_dependencies` 任一成员变化时失效（manifest-diff check on promotion）。
  - 变更分类：`BREAKING`（须重跑）/ `COMPATIBLE`（claim 仍有效）/ `SUPERSEDED`（新证据替换旧）。
- Breaking 变更（清单）：算法源码/依赖版本/场景 YAML/ENC 数据集/evaluator profile/plant 参数/tracker 配置/runtime fingerprint。
- Compatible 变更：保持 hashable 内容一致的 cosmetic rename / 新增非 canonical 场景 / 同 spec replay。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-82 · G3 是否要求 canonical set 零失败及可行超时政策

- [R48] evaluator 硬门已存在为物理/安全 outcome：`PairEvaluation.collision`（`evaluator.py:33`，`min_distance <= 0.5·(length_a+length_b)`）与 `VesselEvaluation.grounded`（`evaluator.py:42`，`grounding_distance <= length/2`）。
- [R8] 架构文档失败语义：含 fallback 的 episode 不得计入目标算法成功率（既有零容忍政策）。
- G3 = capability demonstration（须可观察）；G4 = statistical pass。但 G3 仍要求可观察能力，collision/grounding 会否定之。
- **G3 须零硬门失败**——collision/grounding 与"可观察避碰能力"不相容。无源允许对物理碰撞 outcome 取平均作安全 claim。
- [R9] `TIMEOUT_FEASIBLE` 已定义但**未接入任何 gate decision**（runner 只在 exception/ColavExecutionError/session state 分支）。
- `TIMEOUT_FEASIBLE` 政策（DESIGN_CANDIDATE，非裁决）：G3 视为**soft gate 非 PASS**——仅当 (a) 无硬门失败 AND (b) lateness 有界（记录 max overshoot，无超 `t_max` 的 missed deadline）时计入 capability demonstration；G4（real-time-ready）计为**失败**。manifest 记 `TIMEOUT_FEASIBLE` 频率/cell 供审计。
- NOT_EVALUATED 政策：`NOT_EVALUATED` ⟹ cell **不能 G3**（留 G2 或以下）；`persist_failure()` 已设 `reproduction_status="not_evaluated"`。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-83 · Web 汇总一个算法多个 capability profile 等级的方式

- [R11] capability 已是 per-combination 而非 global。`CapabilityCatalog.validate()` 返回 `{rule}:{scenario}:{algorithm}:{tracker}` 4-tuple（`capabilities.py:359`），每 `Capability` 自带 `readiness_grade/supported_rules/supported_scenarios/known_failure/latest_evidence`。
- Web 已渲染此粒度：`app.js` 读 `status.readiness_grade` 与 `selectable` per algorithm/tracker/scenario card，`incompatibility_reason` 作 tooltip。`GET /api/capabilities?validation_rule_id=...` 返回 per-cell G0-G4 + failure reasons。
- Algorithm-Capability-Matrix.md §3.1 "Rule 14 首个正式能力矩阵" 已展示 per-(tracker×algorithm) cell 形式（God/KF × Nominal/VO/SB-MPC）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - per-cell matrix（行=supported rules/scenarios，列=trackers），每 cell 显示 grade chip（G0-G4）+ selectable/disabled + 一行 `known_failure`。
  - per-algorithm aggregate badge = 其 selectable cells 的**最小 grade**（headline = 最弱 cell），防单一强 cell 高估整体能力；matrix 按需展开。
  - per-cell evidence drill-down（`latest_evidence`: seed/min distance/collision-grounding flags/reproduction_status/capability_profile_id）。
  - 不用单一全局"algorithm readiness"数而无 matrix。
- HCI 证据：**UNKNOWN**——无同行评审 HCI 研究 prescribe capability-matrix presentation for safety/algorithm-readiness UIs。上述为项目既有 pattern + 一般信息密度原则，非证据支持。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-84 · 资格任务自动晋级是否需要人工审核/签名

- [R69] DO-178C 要求 verification independence：验证活动须由独立于开发者的人员执行（§6）。DO-330 定义 TQL-1..5——欲跳过人工验证须鉴定自动化工具（TQL），未鉴定则不可。
- [R70] ISO 26262 Part 8 §11：TD1/2/3 基于"工具错误会被人工审核/验证/输出检查检测"的置信度；高 TD（TD1）可降 TCL 3→1；**移除人工审核升高所需鉴定等级**。最直接的标准支持"人工审核推荐"。
- [R71] IEC 61508 Part 3：通用功能安全软件 V&V。
- [R27] NASA-STD-7009B：M&S credibility 绑定 use case；接受仿真结果为某用途是 judgment，非自动属性——隐含人工接受。
- 海事特定（DNV/IMO）auto-promotion sign-off guidance：**无直接 cited standard**（诚实 gap）。最接近的类比（DNV ASTATOS / DNV-OSS simulator V&V）强调仿真器独立验证，非 auto-promotion 政策。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - **是，即使研究 Playground 也要求人工审核 auto-promotion**：
    1. canonical G3 set 本身**人工批准 + 版本冻结**（人签 off 哪些 scenario 参数化构成 canonical regression set，冻结其 hash）。
    2. auto-promotion 计算 candidate grade；**人须批准后才发布**到 Web catalog（auto-promotion 工具 = 未鉴定验证工具，依 DO-178C/ISO 26262 其输出不可独立成立）。
    3. audit trail：每次 grade 变更记录 (a) 产出它的 manifest hashes（`capability_dependencies`，BL-81），(b) auto-promotion 工具版本，(c) approver identity，(d) timestamp。`RunManifest` 已记 (a)；须加 approver + tool version。
    4. **demotion 自动即时**（canonical set 上失败 run 立即降 cell 到 G2/以下，不等人工）——因 failure 是安全相关事实，非 judgment。仅 **promotion** 需人工。
- 证据边界：可冻结"promotion 需人工 + demotion 自动 + audit trail"；DO-178C/ISO 26262 迁移到研究 Playground 是 recommendation 非义务；maritime 特定标准 UNKNOWN。
- 状态：证据已登记，未标闭环，等待用户确认。

#### 本批用户确认门

- 待用户分别确认 BL-80、BL-81、BL-82、BL-83、BL-84 的证据是否回答原问题。
- 建议确认口径：
  - BL-80：canonical G3 = t=2 covering array（≥16/rule family）× 3 seeds × G3-eligible cells，零硬门失败；G4 保留 range(30)+CI；具体 t/seed 数后置。
  - BL-81：manifest 增 `enc_hash` + 显式 `capability_dependencies` 聚合；失效规则 = 任一成员变化；变更分类 BREAKING/COMPATIBLE/SUPERSEDED。
  - BL-82：G3 须零硬门失败；TIMEOUT_FEASIBLE 为 G3 soft gate 非 PASS、G4 失败；NOT_EVALUATED 不能 G3。
  - BL-83：per-cell matrix + aggregate badge = 最小 grade + evidence drill-down；HCI 证据 UNKNOWN。
  - BL-84：promotion 需人工审核 + audit trail；demotion 自动即时；maritime 特定标准 UNKNOWN。
- 未确认前不改盲区为"已闭环"，不进入 Step4，不实施代码。

### Step3 · 第十一/十二批证据用户确认 [2026-07-28]

- 用户批量确认第十一批 C 档（BL-90..94, BL-95..99, BL-100..103, BL-104..108, BL-114..118，共 24 项）与第十二批 A 档（BL-80..84，共 5 项）。
- C 档 24 项全部闭环（含边界闭环），详见各 BL 注册表。
- BL-80 边界闭环：canonical G3 = t=2 covering array（≥16/rule family）× 3 seeds × G3-eligible cells，零硬门失败；G4 保留 range(30)+CI；具体 t/seed 数后置。
- BL-81 闭环：manifest 增 `enc_hash` + 显式 `capability_dependencies` 聚合；失效规则 = 任一成员变化；变更分类 BREAKING/COMPATIBLE/SUPERSEDED。
- BL-82 闭环：G3 须零硬门失败；TIMEOUT_FEASIBLE 为 G3 soft gate 非 PASS、G4 失败；NOT_EVALUATED 不能 G3。
- BL-83 闭环：per-cell matrix + aggregate badge = 最小 grade + evidence drill-down；HCI 证据 UNKNOWN。
- BL-84 边界闭环：promotion 需人工审核 + audit trail；demotion 自动即时；DO-178C/ISO 26262 迁移为 recommendation；maritime 特定标准 UNKNOWN。
- Step3 尚未完成；不进入 Step4。

### Step3 · 第十三批深度调研（A 档）：DP-23 任务、控制与求解指标 [2026-07-28]

#### 取证摘要

- 本批为 A 档深度调研第三组，对应 DP-23 任务/控制/求解指标的 BL-75..79。
- **NLM 笔记本本批未可用**：`notebooklm login` token 过期，需交互式浏览器 OAuth，subagent 无法执行。已按 fallback 规则全部走 primary source（Woerner 2016 MIT PhD 全文、Tengesdal 2023 CCTA、Eriksen 中层 NLP-MPC、Kaplan-Meier 生存分析、Beiranvand 2017 优化算法比较）。
- **R2 文章号确认**：Hagen et al. 2023, Ocean Engineering 288:**115991**（DOI 10.1016/j.oceaneng.2023.115991）经 Crossref API 权威验证正确，日志原 R2 引用成立，不作修改。
- 新增 primary source：[R73] Eriksen 中层 NLP-MPC（IPOPT solve time 与硬件）；[R74] Kaplan-Meier 生存分析（删失处理）。[R72] Beiranvand 2017 已在 BL-77/79 登记。Woerner 2016 [R62]、Tengesdal CCTA [R1] 已存在。

#### BL-75 · goal/rejoin 的位置、航向、速度和保持时间阈值

- [R62] Woerner 2016 §6.1.1：goal/capture radius 是 designer/mission-dependent 选择，非论文强制数值；"capture radius"取决于任务定义。
- [R1] Tengesdal & Johansen 2023 CCTA：framework 级 metric grouping，数值定义延迟到 Hagen 2022 PhD thesis。
- [R38] 当前 `determine_ship_goal_reached()` 默认半径 `7×length`（Viknes 59.15m），只查位置（BL-54 已确认）；`route_exit` vs `terminal_state` 双模式已闭环（BL-54）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - `route_exit`：cross-track error（corridor half-width）、terminal heading error、along-track progress（route 完成分数）、forward speed > 0；阈值 profile 化，可随船长度尺度（参考 Viknes scale）。
  - `terminal_state`（berthing）：位置/航向/速度/hold-time 容差；典型 berthing 文献值待 `ship_maneuvering` 笔记本重认证后查。
  - 两者都是 versioned profile 参数，非法规硬事实。
- 证据边界：可冻结"profile 化 + route_exit/terminal_state 分离"；`route_exit` 具体数值、`terminal_state` berthing 容差 UNKNOWN（需 ship_maneuvering 笔记本或目标船数据）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-76 · 不同输出控制形式下统一 tracking metric 的方法

- [R62] Woerner 2016 §4.2：效率/任务指标基于闭环执行轨迹（闭环 outcome），非原始控制输出形式。
- [R32] 当前算法输出形式不一：VO/SB-MPC 输出 [course, speed] 参考；潜在 Custom MPC 输出 [force, yaw_moment]；PSB 输出 [speed_scale, course_offset]。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - tracking error 统一针对**执行后闭环轨迹**（regardless of control form），非原始控制输出。
  - 控制努力指标（总舵用量、总推力、速度变化）单独报告，与 reference-tracking 指标分开。
  - 不同 control_form 的算法通过 `AlgorithmDescriptor.control_form`（BL-22）声明，tracking metric 在闭环层面统一。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-77 · 不同 solver 的 iteration/objective 可比边界

- [R62] Woerner 2016 §6.1.1：solver 内部数值（iterations、objective）依赖求解器类型，不可直接比较。
- [R72] Beiranvand, Hare & Lucet 2017：明确不同优化算法的 objective 不可直接比较除非归一化；iterations 计数语义跨求解器不同（SQP iteration ≠ CE sampling iteration ≠ DRL forward pass）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - `solver.iterations` 与 `objective` **不横向比较**跨求解器类型。
  - 可比较的：wall-clock time（带 runtime fingerprint）、feasibility rate、constraint violation、outcome（collision/grounding/arrival）。
  - objective 若需比较，须归一化（如除以初始 objective 或参考 baseline）。
- 证据边界：可冻结"不横向比较 + 可比较项清单"；归一化方法待实现期裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-78 · 提前终止和未到达 run 的统计/删失方法

- [R74] Kaplan-Meier / 生存分析：collision 是**观察到的吸收事件**（observed terminal event），**非删失**；timeout-without-arrival 是**右删失**（right-censored）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - collision/grounding at t=120s（episode 600s）：**FAILED**（硬失败，非删失）；不插补 counterfactual arrival time。
  - timeout（无 collision 无 arrival）at t=600s：arrival time **右删失**；用 Kaplan-Meier + confidence band 报告 arrival-time 分布；**绝不**插补假 arrival time（如 episode_max），否则偏向不稳定算法。
  - 连续指标（path length、control effort）：仅在 pre-failure prefix 计算 OR 完全排除——文献分裂，两种都报告，标注。
  - 失败 run 保留在分母（BL-63 已确认四态聚合）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-79 · deadline 使用开发机、目标硬件或归一化预算

- [R73] Eriksen 中层 NLP-MPC：IPOPT solve time 在命名硬件（2.8 GHz Core i7）上报告；明确"Guaranteeing a maximum computational time for NLPs is difficult"。
- [R72] Beiranvand 2017：wall-clock 依赖语言/硬件/编译器；建议用 function-evaluation 计数或归一化预算做公平比较。
- [R62] Woerner 2016 Appendix C "Normalized Helm Iteration Length" = solve_time / control_period（RT-factor 概念雏形）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 无海事源强制特定 deadline 政策。
  - 报告 wall-clock **AND** 归一化预算（RT-factor = solve_time / control_period）；跨算法公平性强制归一化预算；wall-clock 作性能诊断。
  - 硬件环境进 runtime fingerprint（BL-60）。
- 证据边界：可冻结"wall-clock + RT-factor 双报告 + fingerprint"；具体 RT-factor 阈值待裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

#### 本批用户确认门

- 待用户分别确认 BL-75、BL-76、BL-77、BL-78、BL-79 的证据是否回答原问题。
- 建议确认口径：
  - BL-75：route_exit/terminal_state 双模式 profile 化；具体数值后置（ship_maneuvering 笔记本重认证后查）。
  - BL-76：tracking error 统一针对闭环执行轨迹；控制努力单独报告；control_form 声明。
  - BL-77：iterations/objective 不横向比较；可比较 wall-clock/feasibility/violation/outcome；归一化后置。
  - BL-78：collision=FAILED 非删失；timeout=右删失用 KM；不插补假 arrival；连续指标两种报告。
  - BL-79：wall-clock + RT-factor 双报告；硬件进 fingerprint；RT-factor 阈值后置。
- 未确认前不改盲区为"已闭环"，不进入 Step4，不实施代码。

### Step3 · 第十四批深度调研（A 档）：DP-25 公平 episode、seed 数与统计政策 [2026-07-28]

#### 取证摘要

- 本批为 A 档深度调研第四组，对应 DP-25 统计政策的 BL-85..89。
- **NLM 笔记本本批未可用**（`safety_verification`/`silhil_platform` token 过期）。全部走 primary statistics/simulation 源：[R46] Ehrlichman & Henderson 2008（全文）、[R74] Kaplan-Meier 1958、[R75] Koehler 2009、[R76] Wilson 1927（经 NIST handbook）、[R77] Efron 1979、[R78] Wilcoxon 1945、[R79] Little & Rubin 2020。
- 跨 BL 核心发现：DP-25 全部 rests on [R46] §1 的**配对比较框架**——估计 `E(X−Y)` via paired differences；CRN（及 keyed-CRN）只为减少该配对估计量的方差（共享外生输入）。这是 DP-25 的单一 load-bearing 统计思想。
- 两项是 ENGINEERING（非文献强制）：①keyed-CRN key scheme（BL-88）；②任何特定 seed count（BL-85）。两者是 primary principle 的合理实例化，但无 primary source mandate 其精确形式。

#### BL-85 · G4 所需 seed 数和统计功效

- [R75] Koehler 2009 verbatim："it seems unlikely that a single choice for R [replications] will provide practical guidance in a broad range of simulation settings"；"the magnitude of MCE, and thus the number of replications required, depends on both the design and the target quantity of interest."
- [R46] §1（p.245-246）：比较估计量是配对均值 `E(X−Y) ≈ (1/n)Σ(X_j − Y_j)`；"It is crucial that the random vectors (X_j, Y_j) be IID in order for the usual limit theorems to hold." seed count 作为 n 驱动该配对均值的标准误；方差缩减（CRN）减少所需 n。
- Simio SASMAA7 教科书："we decided, essentially arbitrarily, to make 50 IID replications"——教科书承认 round-number 是启发式非统计要求。
- 正确基础：a-priori/sequential precision targeting——选初始 n₀，从 pilot 估计 s，计算 CI half-width，加 replication 直到 half-width/relative-error γ 满足。无 primary source 给通用 n。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - **不硬编码"30 seeds"**。G4 seed count 由 pre-registered precision target on paired difference 定义（报告 CI half-width；可选 relative-error stopping rule）。
  - 对 min-distance/arrival-time paired comparison，可辩护起始区间 ~20-50 paired seeds with pilot，再 sequential addition to declared half-width——但数量须由 observed variance 论证，非 assertion。
- 证据边界：可冻结"precision-target + 配对差值"；具体 n 与 stopping rule 待 DP-25 裁决，标 UNKNOWN。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-86 · tuning、qualification、holdout 场景划分

- 标准 ML holdout 纪律（Stone 1974 / Geisser 1975 奠基；train/validation/test discipline）：
  - validation set = 调参期间 held back 估计 skill（model selection/hyperparameters）。
  - test/holdout set = 最终无偏泛化评估；触碰一次，不用于任何 modeling decision。
  - 反复检查 holdout performance 并据此调整模型会过拟合 test set（optimistic bias）；holdout 须冻结。
  - evaluator profile 本身是 fit 到数据的 model → 在 tuning data 上冻结、永不在 qualification/holdout 上 re-fit 是该纪律的直接应用。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 三个不相交 corpus：**tuning**（evaluator profile/thresholds/weights 可在此 fit）、**qualification**（G3 canonical hard-gate；frozen evaluator 应用；永不用于 refit）、**holdout**（最终报告比较；触碰一次）。
  - G3 canonical set 属 **QUALIFICATION 非 tuning**。
  - evaluator profile 在 tuning 上冻结，此后不再 refit。
  - 要求是 disjointness/no-look-ahead，非特定比例。
- 证据边界：可冻结"三不相交 + no-look-ahead"；具体划分比例 UNKNOWN（无源强制 70/30 等）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-87 · 失败率、删失时间和连续指标的置信区间方法

- **Failure-rate CI（proportions）**：[R76] Wilson 1927（经 NIST/SEMATECH §7.2.4.1 + Brown, Cai & DasGupta 2001 / Agresti & Coull 1998）。NIST handbook verbatim：Wilson interval "recommended by Brown, Cai and DasGupta (2001) and Agresti and Coull (1998)"，"worth does not strongly depend upon the value of n and/or p"，"lower limit cannot be negative"；Wald 的缺陷："A confidence limit approach that produces a lower limit which is an impossible value...is an inferior approach"。公式 `L/U = [p̂ + z²/(2n) ∓ z·sqrt(p̂(1−p̂)/n + z²/(4n²))] / [1 + z²/n]`。**用 Wilson score（或 Agresti-Coull / Clopper-Pearson exact for tiny n），非 Wald**。尤其小 n 或 rate 近 0/1（crash rate 通常近 0）。
- **Arrival-time CI under censoring（timeouts）**：[R74] Kaplan & Meier 1958（product-limit estimator + Greenwood variance）。KM 1958 本身不给 confidence band——band 是 Greenwood pointwise CI 与后续 simultaneous bands（Nair 1984；Hall & Wellner 1980）。cite KM 1958 for estimator；cite Greenwood/Nair/Hall-Wellner for bands。§1 要求"the lifetime ... is independent of the potential loss time; in practice this assumption deserves careful scrutiny"——timeout 作右删失 arrival time 须论证独立性，非假设。**用 KM + Greenwood CI for censored arrival-time distribution；报告 median arrival time + CI**。
- **Paired continuous metric（paired min-distance/arrival-time difference）**：paired t-test if paired differences ~normal；否则 Wilcoxon signed-rank；bootstrap CI on paired difference 作 distribution-free alternative。[R78] Wilcoxon 1945（signed-rank test 比较 two matched sample location——配对两算法设置直接适用）。[R77] Efron 1979 §2 三步法 verbatim："1. Construct F̂, putting mass 1/n at each point ... 2. draw a random sample of size n from F̂ ... 3. Approximate the sampling distribution of R(X,F) by the bootstrap distribution of R*." → bootstrap CI on paired-difference mean/median 是 primary-sanctioned distribution-free 方法。
- **Small n（canonical set）**：n 小时 proportion CI 宽、Wald 不可用；Wilson/Clopper-Pearson 仍有效但可能 uninformative。对 tiny canonical G3 set，报告 raw paired differences + descriptive stats + nonparametric CI；formal hypothesis tests 留给更大 G4 multi-seed corpus。无源禁止小 n 报 CI，但精度低——诚实报告。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - failure-rate → Wilson score。
  - censored arrival time → KM + Greenwood。
  - paired continuous → paired t if normal else Wilcoxon signed-rank，bootstrap CI 作 robust default。
  - small canonical n → descriptive + nonparametric CI；formal tests 留 G4。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-88 · KF 下路径相关 Sensor 可见性的公平比较方法

- [R46] Ehrlichman & Henderson 2008 全文 verbatim：CRN 严格定义在 **EXOGENOUS INPUT STREAMS**，非 measurements/state。"Common random numbers (CRN) involves using the same streams of uniform random variates **as inputs** for both systems to sharpen the comparison"（abstract）；"common random number sampling entails using identical sequences UX = UY = U = (U1, U2, ...) of pseudorandom variates to compute both X and Y"（§2）。CRN couples "the **joint distribution of the inputs** of both systems."
- CRN 目的是配对差值方差缩减：if `cov(X_j,Y_j)>0 then var(X_j − Y_j) < var X + var Y`（§1）——即 CRN sharpens *paired estimator of E(X−Y)*，仅此。
- [R46] 对同步 *measurement process* 或 *observed sensor stream* **只字未提**；couple 的对象是 uniform input variates U。X 和 Y 是否产生相同 observations 是 model 的 downstream consequence，非 CRN 要求。
- [R46] §2 明示其 finite-dimensional-input 假设"may limit the situations in which the approach we discuss below is applicable"——作者标记 scope limit，不扩展 CRN 到 state-dependent measurement coupling。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - keyed-CRN（BL-59 已闭环）保留用于**外生 sensor-noise draws**（解耦 call order，隔离算法效应）。
  - **不**跨算法同步 realized measurement stream / visibility——那是真实闭环系统差异，须测量非消除。
  - God-profile vs KF-profile 作独立实验比较（BL-59 已确认）。
  - keyed-CRN 标为 [R46] principle 的**工程实例化**，非文献强制。
- 证据边界：可冻结"CRN 仅外生输入 + visibility 是系统属性"；keyed-CRN 具体形式为 ENGINEERING（无 primary 验证）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-89 · 无输出 crash/timeout 在连续指标中的呈现方式

- [R79] Little & Rubin 2020 Ch.1 §1.3 verbatim：Definition 1.1 "Missing data are unobserved values that would be meaningful for analysis if observed; in other words, a missing value hides a meaningful value." MCAR（Eq 1.1）"does not depend on the values of the data, missing or observed"；MAR（Eq 1.2）"depends on y_i only through the observed components"；MNAR "if the mechanism depends on y_i, then the mechanism is MNAR because it depends on values of y_i, some of which are missing." Complete-case analysis（丢弃 incomplete cases）"generally inappropriate because the investigator is usually interested in making inferences about the entire target population, rather than about the portion ... that would provide responses on all relevant variables."
- crash/timeout 应用：crashed/timed-out run **无** arrival time/path length——但 missingness 由算法自身不稳定性驱动（与 would-be outcome 相关的属性）。这是 **MNAR**（或至多 MAR conditional on algorithm），**非 MCAR**。丢弃这些 run 正是 Little & Rubin 称"generally inappropriate"的 complete-case analysis → 向不稳定算法的 survivorship bias。
- failure 本身是信号，非 nuisance。连续指标因 run 失败而 undefined；failure 的正确证据单位是 failure **RATE**（分母 = n_attempted），单独经 Wilson CI 报告（BL-87）。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 每 run 持久化 `(n_attempted, n_completed, n_crashed, n_timeout, n_no_output)`（匹配 DP-26 六件证据包）。
  - 连续指标 CI 仅在 `n_completed` 上计算，n 显式标注。
  - Failure rate（crash+timeout+no_output over n_attempted）经 Wilson CI 报告。
  - **绝不**插补假 arrival time（如 episode_max）——为 MNAR missing observation 伪造"complete-case"值，偏向不稳定算法。
  - 若单一组合指标真正需要，用生存分析（KM）将 crash 作 terminal event / 右删失于 crash time——但即使如此 failure 须计为 failure，非 episode_max 处的成功 arrival。
- 状态：证据已登记，未标闭环，等待用户确认。

#### 本批用户确认门

- 待用户分别确认 BL-85、BL-86、BL-87、BL-88、BL-89 的证据是否回答原问题。
- 建议确认口径：
  - BL-85：不硬编码 seed 数；precision-target on paired difference；~20-50 起始 + sequential；具体 n 后置。
  - BL-86：tuning/qualification/holdout 三不相交 + no-look-ahead；G3 属 qualification；evaluator 在 tuning 冻结。
  - BL-87：failure-rate→Wilson；censored arrival→KM+Greenwood；paired continuous→paired-t/Wilcoxon/bootstrap；small n→descriptive+nonparametric。
  - BL-88：CRN 仅外生输入；不同步 visibility；keyed-CRN 标 ENGINEERING；God/KF 分 profile。
  - BL-89：n_attempted/completed/crashed/timeout 持久化；连续 CI 仅 completed；failure rate Wilson on attempted；绝不插补。
- 未确认前不改盲区为"已闭环"，不进入 Step4，不实施代码。

### Step3 · 第十三/十四批证据用户确认 [2026-07-28]

- 用户批量确认第十三批（BL-75..79）与第十四批（BL-85..89）。
- BL-75 边界闭环：route_exit/terminal_state 双模式 profile 化；具体数值后置。
- BL-76 闭环：tracking error 统一针对闭环执行轨迹；控制努力单独报告；control_form 声明。
- BL-77 边界闭环：iterations/objective 不横向比较；可比较 wall-clock/feasibility/violation/outcome；归一化后置。
- BL-78 闭环：collision=FAILED 非删失；timeout=右删失用 KM；不插补假 arrival；连续指标两种报告。
- BL-79 边界闭环：wall-clock + RT-factor 双报告；硬件进 fingerprint；RT-factor 阈值后置。
- BL-85 边界闭环：不硬编码 seed 数；precision-target on paired difference；~20-50 起始+sequential；具体 n 后置。
- BL-86 闭环：tuning/qualification/holdout 三不相交+no-look-ahead；G3 属 qualification；evaluator 在 tuning 冻结。
- BL-87 闭环：failure-rate→Wilson；censored arrival→KM+Greenwood；paired continuous→paired-t/Wilcoxon/bootstrap；small n→descriptive+nonparametric。
- BL-88 闭环：CRN 仅外生输入；不同步 visibility；keyed-CRN 标 ENGINEERING；God/KF 分 profile。
- BL-89 闭环：n_attempted/completed/crashed 持久化；连续 CI 仅 completed；failure rate Wilson on attempted；绝不插补。
- Step3 仅剩 BL-109..113（PSB/RLMPC 归一化，DP-30）未调研；不进入 Step4。

### Step3 · 第十五批深度调研（A 档）：DP-30 外部 MPC 输出归一化 [2026-07-28]

#### 取证摘要

- 本批为 A 档深度调研最后一组，对应 DP-30 外部 MPC 输出归一化的 BL-109..113。
- 全部证据来自 primary source code verbatim（C++ header/body + Python class，带文件:行号），权威性 A。
- [R43] PSB-MPC 源码深化：`psbmpc/external/thecolavrepo/psbmpc_cxx/psbmpc_lib/`（C++ core）、`psbmpc_interface/src/PSBMPC_interface.cpp`（pybind binding）、`configs/psbmpc.yaml`。
- [R44] RLMPC 源码深化：`rlmpc/rlmpc/mpc/models.py`（Viknes L500）、`rlmpc/mpc/trajectory_tracking/{ttmpc,acados_mpc,casadi_mpc}.py`、`rlmpc/mpc/common.py`（AcadosErrorCode L75）、`config/ttmpc.yaml`。
- **发现 2 个 playground 集成 latent bug**（不影响归一化设计，但须标记修复）：
  1. `KinematicShip` 构造参数误绑：两 wrapper 把 `dt_predictor=15.0/dt_sim=0.5` 传入 7-arg 构造 `(l,w,T_U,T_chi,R_a,LOS_LD,LOS_K_i)`，实际落入 `LOS_LD=15.0`（lookahead distance）和 `LOS_K_i=0.5`（LOS 积分增益），非预测步长。真正预测步长来自 `pars.dt`。
  2. `AcadosMPCWrapper`（`custom_mpc_adapter.py:481-491`）调用 `TrajectoryTrackingMPC.solve()`——**该方法不存在**（只有 `plan()`）；读 `sol.get("x_pred")`——**该 key 不存在**（实际 key 是 `"trajectory"`）。导致 RLMPC 路径永远异常→永远 fallback `SimpleLinearMPC`。

#### BL-109 · PSB-MPC 原生 state/control layout 和 horizon 时间语义

- [R43] native ownship state = `[x, y, chi, U]`（4-dim），**非** `[x,y,Vx,Vy]` 也**非** `[x,y,cog,sog]`-as-velocity。`kinematic_ship_models_cpu.cpp:463` 注释 `State [x, y, chi, U]`；`:477-478` 动力学 `xs_new(0)=xs_old(0)+dt*xs_old(3)*cos(xs_old(2))`。`chi`=course（heading over ground），`U`=SOG。
- [R43] control 输出是两标量：`u_opt`（surge multiplier，无量纲）与 `chi_opt`（course offset，弧度）。`psbmpc_cpu.hpp:45-50` struct `optimal_offsets_results_py { double u_opt_py; double chi_opt_py; Eigen::MatrixXd predicted_trajectory_py; }`。
- [R43] `calculate_optimal_offsets` 签名（`PSBMPC_interface.cpp:863-876`）：`(u_d, chi_d, waypoints[2,N], ownship_state[4], V_w, wind_direction[2], polygons[], obstacles[], new_static_obstacle_data, disable)` → `optimal_offsets_results_py`。
- [R43] **native predicted trajectory 存在且是真实 plant prediction**（非合成）。`psbmpc_cpu.cpp:580-581` `trajectory.resize(ownship_state.size(), n_samples); trajectory.col(0) = ownship_state;` 然后 `:598` `ownship_ptr->predict_trajectory(...)`。`assign_optimal_trajectory`（`:1379-1385`）：`optimal_trajectory = trajectory.block(0,0,rows,n_samples)`。
- [R43] shape = `(4, n_samples)`，`n_samples = round(pars.T / pars.dt)`（`psbmpc_cpu.cpp:578`）。4 行 = `[x, y, chi, U]`。**列 0 = 当前状态（t=0），列 1..N-1 = 未来**（`:581` `trajectory.col(0)=ownship_state`）。
- [R43] T 和 dt 来自 `PSBMPC_Parameters`，非 ship。`set_par_double(0,T)`, `set_par_double(1,dt)`（`PSBMPC_interface.cpp:86-89,156-159`）。config `psbmpc.yaml` native `T:120, dt:1.0` → 120 samples；playground override T=15, dt=0.5 → 30 samples。
- [R43] KinematicShip 7-arg 构造 = `(l, w, T_U, T_chi, R_a, LOS_LD, LOS_K_i)`（guidance/kinematic 参数），**非** `(length,width,draft,U_max,U_min,dt_predictor,dt_sim)`。`kinematic_ship_models_cpu.hpp:65-72`。
- [PROJECT_FACT] 正式 `PSBMPCColav`（`integrations/psbmpc.py:183`）**正确读** `result.predicted_trajectory`；legacy `PSBMPCWrapper`（`custom_mpc_adapter.py:307-312`）**丢弃** native trajectory 并合成常速 horizon——是 wrapper artifact 非 native 限制。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - `TrajectoryMapping.psbmpc`：native `(4,N)` `[x,y,chi,U]` col-0=current → public `(9,N)` `[x,y,psi,u,v,r,x_ddot,y_ddot,psi_dot]`。`psi:=chi`，`u:=U*cos(chi)`，`v:=U*sin(chi)`（或 `u:=U, v:=0`——需裁决；PSB native 假设 course-aligned 故 `v=0` 是 native 假设），`r,x_ddot,y_ddot,psi_dot` 经 finite-diff（estimated=true）。col-0 保持 t=0。
  - control：public "reference" 输出 = `(u_d*u_opt, chi_d+chi_opt)`，非绝对控制。
- 证据边界：可冻结"4xN [x,y,chi,U] + col-0=current + native plant_prediction"；`v` 的处理（`U*sin(chi)` vs `0`）待裁决。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-110 · RLMPC `6xN` 状态、控制和 reference 的精确映射

- [R44] 默认/active model = `Viknes`（3DOF dynamic），state `[x, y, chi, U, V, r]`。`models.py:500` `class Viknes(MPCNode)`；`:537` `dims()->(6,2)`；`:545-546` `u = csd.MX.sym("u",2) # Fx, Fy`；`:558` `C = mf.Cmtrx_casadi(...)`；`:566-568` `Rpsi @ x[3:6]`。`x[2]=chi`，`x[3:6]=[U,V,r]`（surge, sway, yaw rate）。`ttmpc.py:45` default `model=...Viknes()`；`ttmpc.yaml` `model: {viknes: ""}`。
- [R44] control = `[Fx, Fy]`（2-dim：surge force, sway force）。`models.py:545`。yaw moment 经 `B=[[1,0],[0,1],[0,-l_r]]`（`:569`）——Fy 经 lever `l_r` 产生 yaw，**非纯 `[thrust, yaw_moment]`**。
- [R44] 另两个 6-state model 存在但**非 TT-MPC 默认**：`AugmentedKinematicCSOG`（`:97-183`）state `[x,y,chi,U,chi_d,U_d]`；`KinematicCSOGWithAccelerationAndPathtiming`（`:309`）state `[x,y,chi,U,s,s_dot]`。
- [R44] horizon：T=40.0, dt=0.5 → N=80 shooting nodes（`ttmpc.yaml`；`trajectory_tracking_mpc.py:113`）。
- [R44] reference = `nominal_trajectory`（LOS-based），shape `(6, N)`，**非** `(2,N)`。`trajectory_tracking_mpc.py:117-121` `create_los_based_trajectory(...)` → `nominal_trajectory`；`:157` 索引 `nominal_trajectory[2,:]`（chi row）。
- [R44] 默认 solver 是 CasADi/IPOPT，**非 acados**（macOS arm64 不兼容）。`ttmpc.yaml` `enable_acados: False`；`ttmpc.py:28-33` `if arm64+Darwin: ACADOS_COMPATIBLE=False`。
- [PROJECT_FACT] **playground `AcadosMPCWrapper` 当前对真实 API 不可用**：调用 `self._mpc.solve(...)`（`TrajectoryTrackingMPC` 无此方法，只有 `plan()`），读 `sol.get("x_pred")`（实际 key 是 `"trajectory"`）→ 永远异常 → 永远 fallback。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - `TrajectoryMapping.rlmpc`：native `(6,N)` `[x,y,chi,U,V,r]` → public `(9,N)`。`psi:=chi`，`u:=U`，`v:=V`，`r:=r`（故 `psi_dot:=r` native 存在，无需 finite-diff）。`x_ddot, y_ddot` 经 `[x,y]` 列 finite-diff（estimated=true）。
  - reference mapping：`nominal_trajectory` `(6,N)` → public reference；`nominal_inputs` `(2,N-1)` `[Fx,Fy]`。
- 证据边界：可冻结"6xN [x,y,chi,U,V,r] + r=psi_dot native"；wrapper 须先修复调 `plan()` 读 `"trajectory"` 才谈映射。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-111 · 缺失加速度/航向等字段允许的可验证推导

- [R43] PSB ownship `[x,y,chi,U]`：heading **存在**（`chi`），sway/yaw-rate/accelerations **不存在**。native 运动模型是 single-integrator course/speed（`kinematic_ship_models_cpu.cpp:477-489`），故 `v≡0, r≡0` 是 **native 假设**，非遗漏。
- [R43] PSB obstacle KF state `xs_0 = [x,y,Vx,Vy]`（velocity components，无 heading）。`tracked_obstacle.hpp:50`；`tracked_obstacle.cpp:51-52`。heading **源码内推导**：`tracked_obstacle.cpp:48` `double psi = atan2(xs_aug(3), xs_aug(2))`。这是算法作者对 obstacle 的自有选择——`atan2(Vy,Vx)` 推导有先例。
- [R44] RLMPC Viknes `[x,y,chi,U,V,r]`：`r` IS yaw rate = `psi_dot`（native 存在）。`models.py:558` 用 `x[3:6]=[U,V,r]` 于 Coriolis/damping。`x_ddot`/`y_ddot`（inertial-frame accelerations）**非** state variable。
- [R43][R44] 两 native model 均为 kinematic/dynamic integrator——无 acceleration state。finite-diff `[x,y]` 跨 horizon 列得 inertial accelerations；body-frame `x_ddot,y_ddot` 须额外绕 `chi` 旋转。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：与已闭环 BL-19（missing dims→0, estimated=false）一致，**除了**实际执行推导时：
  - **可验证（closed-form, deterministic）→ estimated=true + method 记录，非 0**：`psi=atan2(Vy,Vx)`（PSB obstacle 先例 `tracked_obstacle.cpp:48`）；RLMPC `psi_dot:=r`（identity，estimated=false）。
  - **finite-diff（numerical, dt-dependent）→ estimated=true, method="finite_diff", record dt**：PSB `x_ddot,y_ddot,psi_dot` 从 `[x,y,chi]` 列；RLMPC `x_ddot,y_ddot` 从 `[x,y]` 列。
  - **真正缺失无推导 → 0, estimated=false（BL-19 默认）**：PSB sway `v` 若 public 契约要求 body-frame sway 而 native 假设 `v≡0`。
- 证据边界：可冻结"method-driven 可验证 vs estimated"；细化 BL-19 的 blanket "missing→0"。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-112 · raw native payload 的证据 schema 和体积

- [R43] PSB native return（`optimal_offsets_results_py`）仅暴露 3 字段：`u_opt`（double）、`chi_opt`（double）、`predicted_trajectory`（`MatrixXd (4, n_samples)`）。`psbmpc_cpu.hpp:45-50`。**无 objective/cost、无 constraint violation、无 n_CE、无 Pr_s、无 target predictions 返回 Python**。
- [R43] PSB 内部存在但不经 return struct 暴露的诊断：`min_cost`（`:67`）、`P_c_i` collision-probability matrix `(n_ps[i], n_samples)`（`:625,741`）、CPE `n_CE=500` samples（`cpe_cpu.cpp:62`）。暴露须自定义 binding 扩展。
- [R44] RLMPC `plan()` return dict（trajectory_tracking，真实）keys：`trajectory, inputs, lower_slacks, upper_slacks, so_constr_vals, do_constr_vals, t_solve, cost_val, n_iter, final_residuals`。`acados_mpc.py:334-345`（acados）/ `casadi_mpc.py:371-382`（casadi，`n_iter` from `stats["iter_count"]`）。**无 `status` key**（见 BL-113）。
- 体积估计/solve：
  - PSB：trajectory `4×n_samples` doubles。playground T=15,dt=0.5 → 4×30=120 floats（~1 KB）。native T=120,dt=1.0 → 4×120=480 floats（~4 KB）。CE-sample arrays（若暴露）`2×500`/obstacle/CPE call——大，candidate for per-solve file（BL-92）。
  - RLMPC：trajectory `6×N` + inputs `2×(N-1)` + slacks。T=40,dt=0.5,N=80 → 6×80+2×79≈638 floats（~5 KB）。`final_residuals` 小。均舒适入 `algorithm_details`（BL-35/38）；标准 payload 无需 per-solve file。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）：
  - 持久化 **struct fields as-returned** 入 `algorithm_details`：PSB `{u_opt, chi_opt, predicted_trajectory_shape}`；RLMPC `{t_solve, cost_val, n_iter, final_residuals, so_constr_max, do_constr_max}`。
  - 大 native arrays（PSB CE samples, full `P_c_i`）→ per-solve file（BL-92）**仅当**自定义 binding 暴露它们；stock binding 不返回，故默认体积小。
  - schema 随 `TrajectoryMapping` adapter 版本化（BL-30）。
- 证据边界：可冻结"stock payload 小 + as-returned 持久化"；PSB objective/constraints 暴露须 C++ binding 改动（out of scope，flag future enhancement）。
- 状态：证据已登记，未标闭环，等待用户确认。

#### BL-113 · PSB/RLMPC native status 到公共状态的映射表

- [R43] **PSB 无 native status/exit-code，无 INFEASIBLE vs NUMERICAL_FAILURE 区分**。`grep` `psbmpc_cpu.cpp` for `throw|assert|runtime_error|exception` 返回**零匹配**。`calculate_optimal_offsets_py` 总返回 result struct；唯一"失败"是 (a) C++ exception 经 pybind 传播（→ Python `Exception`），或 (b) 上游 assertion 的 SIGABRT/segfault。playground `psbmpc.py:187-196` catch `Exception` → `PlanStatus.NUMERICAL_FAILURE`——无 native 更细区分可映射。
- [R44] RLMPC acados status **可用但经 LOCAL vendored enum，非 upstream**。`common.py:75-81`：
  ```
  class AcadosErrorCode(Enum):
      Success = 0; Failure = 1; MaxIter = 2; MinStep = 3; QPFailure = 4; Ready = 5
  ```
  `map_acados_error_code(int)->name`（`:84-85`）。mid_level 捕获 `:511 status=solve()`，`:531 success = status==0`，`:535 qp_failure = (status_str=="QPFailure")`。
- [R44] **重要：此 local enum 与 upstream acados `status_to_str` 不同**（upstream：1=NaN, 2=MaxIter, 3=MinStep, 4=QP_FAILURE, 5=Ready, 7=Timeout, 9=Infeasible）。rlmpc vendored enum `Failure=1`（ambiguous）且**无 Timeout/Infeasible codes**。playground 须映射 rlmpc local enum（实际使用的），非 upstream docs。
- [R44] trajectory_tracking MPC（`TrajectoryTrackingMPC` 用的）**不把 `status` 放 return dict**（`acados_mpc.py:334-345`/`casadi_mpc.py:371-382`）。仅 `mid_level` AcadosMPC 内部捕获。要暴露 RLMPC status，integration 须读 `self._prev_sol_status` 或扩展 wrapper——不在标准 `plan()` 输出。
- 证据支持的契约方向（DESIGN_CANDIDATE，非裁决）——映射表：

  | Native signal | Source | → PlanStatus |
  |---|---|---|
  | PSB: result returned, `disable` path or `!colav_active`（`psbmpc_cpu.cpp:601-616`） | struct returned, `u_opt=1.0, chi_opt=0.0` | SUCCESS |
  | PSB: C++ exception 传播 Python | `psbmpc.py:187` catch `Exception` | NUMERICAL_FAILURE |
  | PSB: SIGABRT/abort from upstream assertion | (BL-13/57) | NUMERICAL_FAILURE |
  | PSB: distinct INFEASIBLE | **NOT DISTINGUISHABLE — UNKNOWN** | (map NUMERICAL_FAILURE; flag) |
  | RLMPC acados `status==0`（Success） | `common.py:76` | SUCCESS |
  | RLMPC acados `status==2`（MaxIter） | `common.py:78`；查 `final_residuals` feasibility | TIMEOUT_FEASIBLE if feasible else INFEASIBLE |
  | RLMPC acados `status==1`（Failure） | `common.py:77` — ambiguous | NUMERICAL_FAILURE（保守）|
  | RLMPC acados `status==3`（MinStep） | `common.py:79` | NUMERICAL_FAILURE |
  | RLMPC acados `status==4`（QPFailure） | `common.py:80`；`mid_level:535` | NUMERICAL_FAILURE |
  | RLMPC acados `status==5`（Ready） | `common.py:81` | SUCCESS（sentinel）|
  | RLMPC casadi/IPOPT（default path） | `casadi_mpc.py:380` `n_iter=stats["iter_count"]`；无 status enum | 从 `n_iter < max_iter(300)` & `final_residuals` 推断 |

- 证据边界：可冻结"PSB 无 INFEASIBLE 区分 + RLMPC local enum 映射表"；RLMPC status 须扩展 wrapper 才能从 `plan()` 获取。
- 状态：证据已登记，未标闭环，等待用户确认。

#### 本批用户确认门

- 待用户分别确认 BL-109、BL-110、BL-111、BL-112、BL-113 的证据是否回答原问题。
- 建议确认口径：
  - BL-109：PSB native `(4,N)` `[x,y,chi,U]` col-0=current；`TrajectoryMapping.psbmpc` 映射；`v` 处理（sin(chi) vs 0）待裁决。
  - BL-110：RLMPC native `(6,N)` `[x,y,chi,U,V,r]`；`r=psi_dot` native；wrapper 须先修复调 `plan()`。
  - BL-111：method-driven 可验证（atan2/identity）vs estimated（finite_diff）；细化 BL-19。
  - BL-112：stock payload 小（PSB ~1-4KB, RLMPC ~5KB）+ as-returned 持久化；PSB objective/constraints 须 binding 改动。
  - BL-113：PSB 无 INFEASIBLE 区分（UNKNOWN）；RLMPC local enum 映射表；status 须扩展 wrapper 暴露。
- **额外标记 2 个 playground 集成 latent bug**（不阻塞归一化设计，但实现期须修复）：
  1. `KinematicShip` 构造参数误绑（`dt_predictor→LOS_LD`, `dt_sim→LOS_K_i`）。
  2. `AcadosMPCWrapper` 调不存在的 `solve()` 读不存在的 `"x_pred"` → 永远 fallback。
- 未确认前不改盲区为"已闭环"，不进入 Step4，不实施代码。

### Step3 · 第十五批证据用户确认 + Step3 完成门 [2026-07-28]

- 用户批量确认第十五批（BL-109..113）。
- BL-109 边界闭环：PSB native `(4,N)` `[x,y,chi,U]` col-0=current；native predicted_trajectory 是真实 plant_prediction；`TrajectoryMapping.psbmpc` 4→9；`v` 处理后置。
- BL-110 边界闭环：RLMPC native `(6,N)` `[x,y,chi,U,V,r]`；`r=psi_dot` native；`TrajectoryMapping.rlmpc` 6→9；wrapper 须先修复。
- BL-111 闭环：method-driven 可验证 vs estimated；细化 BL-19。
- BL-112 闭环：stock payload 小 + as-returned 持久化；PSB objective 须 binding 改动。
- BL-113 边界闭环：PSB 无 INFEASIBLE 区分（UNKNOWN）；RLMPC local enum 映射表。
- **2 个 playground 集成 latent bug 登记**（实现期修复）：KinematicShip 参数误绑；AcadosMPCWrapper 不可用。

#### Step3 完成门检查

- BL-01..BL-118 全部盲区已有证据或标 UNKNOWN/EXTERNAL_CONFIRMATION_REQUIRED；无"未调研"项。
- 证据矩阵 [R1]..[R79] 共 79 条（DOMAIN_EVIDENCE / PROJECT_FACT / DOCUMENTED_INTENT 分层，含三类置信度）。
- 4 个技术分解（TD-01..04）的全部子模块盲区已覆盖：
  - TD-01 Custom MPC 插件契约（DP-08..14）：BL-11..38 全部闭环。
  - TD-02 最小闭环仿真夹具（DP-16..19）：BL-43..60 全部闭环。
  - TD-03 独立评价与资格认证（DP-21..26）：BL-65..89, BL-90..94 全部闭环。
  - TD-04 外部算法 Worker（DP-28..30）：BL-95..108, BL-109..113 全部闭环。
- 三类置信度已分列（检索置信 / 来源权威 / 场景适用）。
- 源身份修正已记录：R51（C²A 非 Connectivity-Based Culling）、R56（MSC.232(82) ECDIS 非 MSC.192(79)）、R58（MSC.192(79) 雷达标准）、R59（Namgung 单作者 Route Planning）、R2（115991 经 Crossref 确认正确）。
- 2 个 NLM 笔记本限制已记录：本会话 token 过期，A 档 BL-75..89 三批未用笔记本（全走 primary source）；后续可重认证后补充。
- **Step3 完成**。不自动进入 Step4；等待用户授权。

## Step4 · 汇总分析·推荐方案 [2026-07-28]

### 用户授权 + 执行计划

- 用户确认 Step3 完成，授权进入 Step4，并要求"给出完整的 MPC Playground 方案"。
- Step3 checkpoint 已提交（`bb15a17`，+1856 行）。
- 执行方式：逐 DP 综合（推荐+证据链+弃用理由+风险量化+失效边界），技术分解完整性校验，冲突显式标注不抹平。分 4 批展示：DP-05..11 / DP-12..18 / DP-19..26 / DP-27..31。

### DP-05 · 标准场景包来源、迁移与溯源

- **推荐**：V1 先认证当前五类标准场景（head_on/crossing_give_way/crossing_stand_on/overtaking/overtaken）；PSB corpus 仅迁移小型固定样本（easy 窗口 More og Romsdal，毫米级几何等价）。每迁移场景保留 raw YAML + normalized episode + migration report 三件套。
- **证据链**：[R1][R3] 主链可继续作唯一仿真/算法边界；[R15][R16] `telemetron→viknes` 改名 + 3600 episode 迁移实测；[R17] easy 窗口几何等价（Hausdorff 0.0015m）；[R18] Kartverket CC BY 4.0 开放许可；[R19][R20] PSB 全量 benchmark 语义 + nominal/constant/variable 配对。
- **弃用**：① 直接把 PSB 3600 episode 当当前可用场景（schema 不兼容 + Agder 缺失）；② 宣称全图版本相同（medium 缺 Agder，历史/当前 GDB 非同一快照）。
- **风险**：中。来源——批量迁移可能静默改变船模/地图/几何，形成"数量多、语义错"的假覆盖。失效边界——迁移须逐字段核验 + 几何等价性测试。验证需求——每个迁移场景通过当前 Cerberus schema + head_on 窗口几何签名比对。
- **DECOMPOSITION**：✓ 闭环（BL-01..03）。

### DP-06 · Playground ODD 与最小覆盖矩阵

- **推荐**：V1 = 四类双船 open-water（Rule 14/15-16/15-17/13）+ God tracker + Viknes synthetic reference plant + 无风流；V2 = ENC 受限 + KF；V3 = multi-ship。AIS/Imazu/VIM/极端海况/非合作目标后置。
- **证据链**：[R22][R24] 当前唯一完整 plant 是 Viknes/FLSC（8.45m，10m/s 上限，dt=0.5s）；[R1][R2] MPC 避碰须覆盖四类双船规则；[R28] FCB45 目标 ODD 保留 EXTERNAL_CONFIRMATION。
- **弃用**：① 一次加入 AIS/Imazu/复杂感知/全部海况（拖垮主线）；② 把 Viknes 结果外推 FCB45（尺度差 5.33×）。
- **风险**：中。来源——范围过窄致几何过拟合；范围过宽拖垮 Playground。失效边界——crossing/overtaking 场景速度超 Viknes 10m/s 上限（当前 15m/s 被钳位），须先修复。验证需求——四类规则各有至少一个 G3 对照算法。
- **DECOMPOSITION**：✓ 闭环（BL-04..07）。

### DP-07 · 算法资格顺序和进入条件

- **推荐**：Nominal 风险基线 → VO/SB-MPC 规则对照 → Custom MPC → PSB-MPC/RLMPC 条件对照。每类规则至少一个 G3 对照算法即可（不要求 VO 和 SB-MPC 各自覆盖全部规则）。Custom MPC 不等外部算法/RRT/VIM。
- **证据链**：[R25] 当前 capability 静态登记，非资格任务自动产物；[R1][R2] 所有对照算法须相同 episode/Tracker/船模/Evaluator。
- **弃用**：① 先集成全部外部算法（PSB/RLMPC 运行时问题遮蔽 Playground）；② 把 import/单步成功当性能基准。
- **风险**：高。来源——错误身份/静默 fallback/自然无风险 nominal 产生不可用比较。失效边界——nominal 必须存在真实风险（BL-09 已确认 head_on DCPA≈0m）。验证需求——Nominal 最小船距低于安全域，证明"无算法介入即有风险"。
- **DECOMPOSITION**：✓ 闭环（BL-08..10）。

### DP-08 · 统一 Custom MPC 插件契约

- **推荐**：正式 Custom MPC 只经 `CustomMPCAdapter(ICOLAV)` 接入；Adapter 负责验证/转换，不实现算法策略。legacy `custom_mpc_adapter.py`（guidance 层 `IGuidance`，含静默 fallback）**不作正式接口**。Adapter 内 typed `PlannerInput` DTO；保持 `ICOLAV.plan()` 签名兼容。`AlgorithmDescriptor` 版本化可哈希 config。
- **证据链**：[R3][R9] `ICOLAV` 稳定边界 + PlannerTrace 已有骨架；[R11] legacy adapter 含硬编码 sys.path + 静默 fallback（ALT-04 弃用）；BL-11..13 闭环。
- **弃用**：① 直接从 `Simulator.step()` 调 solver（耦合场景/单位/失败/诊断）；② legacy `custom_mpc_adapter.py` fallback 路径（无法证明 executed identity）。
- **风险**：中。来源——Adapter 验证不完整致"求解成功但物理错误"。失效边界——坐标/单位/时间有效性/Track 质量/covariance PSD 须 Adapter 验证。验证需求——白盒固定输入测试 + 闭环测试走相同 Adapter。
- **DECOMPOSITION**：✓ 闭环（BL-11..13）。

### DP-09 · Custom MPC 输入语义

- **推荐**：Adapter 内构造 typed `PlannerInput`（ownship/track/enc/reference/seed/identity/time_validity）。Adapter 验证结构/语义（坐标 ENU、单位 SI、Track age profile 化 + degraded 标志、covariance PSD、finite/shape、length/width 缺失→INVALID_INPUT）；solver 判断优化可行性。in-process 传完整 ENC，Worker 传裁剪 hazard geometry + SHA。无效输入显式 `INVALID_INPUT`，不替换 God truth。
- **证据链**：[R3] `do_list` 裸元组无自描述；[R30][R31] Radar NaN 歧义 + VIM 空扫描语义；[R35] ENC 加载慢；BL-14..17 闭环。
- **弃用**：① 用 God truth 替换无效输入；② 静默补默认 covariance/单位阵。
- **风险**：中。来源——ENU/NED、度/弧度、过期 Track、非 PSD covariance 致"求解成功但物理错误"。失效边界——Adapter 须拒绝/降级无效输入。验证需求——白盒注入无效输入测试。
- **DECOMPOSITION**：✓ 闭环（BL-14..17）。

### DP-10 · Custom MPC 输出语义

- **推荐**：`ICOLAV.plan()` 返回控制器兼容参考（`9xN`）；PlannerTrace 保存同一真实求解的完整 horizon。horizon 第 0 列 = solve-time 当前状态；后续 = `t_solve + k*horizon_dt`。`selected_command` 单独字段。`StateMapping` 版本化映射非 9 维 native state（缺失维度填 0 标 `estimated=false`，可验证推导标 `estimated=true+method`）。连续性检查（motion bound 上界）；首点误差 ≤ footprint tolerance。Custom MPC 只有 `9x1` 最多 G2，完整非空 horizon 才进 G3。
- **证据链**：[R3] VOWrapper 首列覆写为当前状态；[R32] SB-MPC 简化 predictor；[R29] trajectory/events 时间相位；BL-18..21 闭环。
- **弃用**：① 只验证 `9xN` shape/finite（漏时间对齐/连续性）；② hold 步重置 horizon 原点。
- **风险**：中。来源——预测/返回计划/执行指令来自不同候选或求解周期，形成假证据。失效边界——horizon 须绑定 solve_id + 连续性 + 首点容差。验证需求——白盒比对 horizon col-0 与 ownship_state。
- **DECOMPOSITION**：✓ 闭环（BL-18..21）。

### DP-11 · MPC 算法声明元数据

- **推荐**：`AlgorithmDescriptor` 强制 12 字段（`algorithm_id/version/control_form/state_layout/predictor_model/horizon_dt/horizon_steps/objective_terms/constraint_terms/solver/seed_policy/execution_profile`）+ 允许 not_applicable 字段。`build_identity` 携带 SHA/binary/solver/build flags（缺失标 UNKNOWN）。静态配置进 Descriptor（冻结），动态值（权重/horizon/mode）进 `algorithm_details` 绑 solve_id。公共 cost/constraint 分类词表；不同算法 objective 不横向比较。
- **证据链**：[R9] `RunSpec.algorithm_config` 无 schema；[R40] manifest identity 字段；[R43][R44] native binary 身份；BL-22..25 闭环。
- **弃用**：① 自由格式 dict（字段缺失/拼写漂移/单位不明/版本不可迁移）；② 把 PSB objective 与 RLMPC objective 直接比较。
- **风险**：低。来源——同名算法跨 run 改变模型/权重/约束污染统计。失效边界——manifest 须冻结 config 副本。验证需求——config hash 比对。
- **DECOMPOSITION**：✓ 闭环（BL-22..25）。

### 第一批用户确认门

- 待用户确认 DP-05..11 的推荐是否可标 final（VR）。
- 建议：批量确认（证据链完整，DESIGN_CANDIDATE 在 Step3 已逐条确认）。
- 未确认前不标 VR final，不进 Step5。

### 第一批用户确认 [2026-07-28]

- 用户批量确认 DP-05..11 推荐。
- DP-05..11 标 VR final（见 0.6 裁决注册表）。
- 技术分解 TD-01 子模块 DP-08..11 全部综合完成。

### DP-12 · `plan/reset` 生命周期与时序

- **推荐**：多率调度；真实求解才增加 `solve_id`。首次 solve 在 `t=0`（`solve_id=1` 首步）。`solve_period` 算法声明 + RunSpec 可覆盖（声明覆盖）。hold 步保留同一 horizon（原点 `t_solve` 不变），执行指令按 `t_now - t_solve` 采样（不重新 solve），`solver_executed=false`。reset 清空 warm start；replay 重新冷启动；无 seed API 的 native 不获 exact 资格。每 episode 独立 seed 完整 reset。离线快速仿真可选关 deadline（`deadline_mode=OFF`），但该 run 标 `diagnostic_only` 不进 G3。
- **证据链**：[R29] 单步相位 + PlannerTrace 时序；[R3] SBMPCWrapper 硬编码 5s 周期；[R44] RLMPC warm start 跨 run 不可复用；[R43] PSB CPE seed；BL-26..30 闭环。
- **弃用**：① 每步求解（改变算法负载）；② hold 步重置 horizon 原点 / 伪增 solve_id；③ 强制离线实时 deadline。
- **风险**：中。来源——非求解步伪增 solve_id / hold 重置原点产生错误执行/重放。失效边界——hold 步须保留 horizon 原点。验证需求——solve_id 单调递增且仅真实 solve 增加。
- **DECOMPOSITION**：✓ 闭环（BL-26..30）。

### DP-13 · 失败状态与 fallback 政策

- **推荐**：正式验证 `strict_no_fallback=true`。失败分类：`SUCCESS/TIMEOUT_FEASIBLE/INFEASIBLE/NUMERICAL_FAILURE/INVALID_INPUT/DEPENDENCY_UNAVAILABLE`（已存在）。`TIMEOUT_FEASIBLE` 可执行当前可行解（非 hold），但计 deadline 失败；连续 `TIMEOUT_FEASIBLE` 阈值 profile 化（超阈 run FAILED，`primary_reason=REALTIME`）；G3 要求零 deadline 失败。`INVALID_INPUT` 归因 `SCENARIO/ADAPTER/ALGORITHM`。native crash 映射 `NUMERICAL_FAILURE`。Web 调试模式可 `hold_on_failure`（标 `diagnostic_only`）。仅 `TIMEOUT_FEASIBLE` 可按后续政策执行，其他失败使正式 run fail-stop。
- **证据链**：[R9] `PlanStatus` 六态 + `strict_no_fallback`；[R43] PSB native abort；BL-31..34 闭环。
- **弃用**：① `except: return previous_plan`（破坏 executed identity/失败率/归因）；② 自动重试有状态 plan。
- **风险**：高。来源——静默 fallback 把崩溃统计为成功 + 旧计划在新冲突中不安全。失效边界——`strict_no_fallback=true` + 失败样本保留分母。验证需求——注入 native crash 确认 fail-stop。
- **DECOMPOSITION**：✓ 闭环（BL-31..34）。

### DP-14 · PlannerTrace 与 solve/hold 语义

- **推荐**：完整 PlannerTrace 只在真实 solve 写入 events；每步 trajectory 只引用 `solve_id` 和实际执行。公共必需 9 字段（`algorithm_id/solve_id/sim_time/solver_executed/status/elapsed_ms/predicted_trajectory/horizon_dt_s/selected_command`）+ MPC 专项必需 4 字段（`objective/iterations/feasible/constraints`）；算法特定诊断进 `algorithm_details`。公共 cost/constraint 分类词表（与 BL-25 共享）；最小裕度 SI 单位进 `constraints`。多模态 target schema `{target_id, mode_id, probability, predicted_trajectory[Nx9], covariance[Nx4x4], source}`。trace 分层：events.jsonl 增量写完整 solve（含 horizon）；trajectory.parquet 每步 state/reference/selected_command；大 horizon（>1000 步 或 >10 目标）拆 per-solve 文件 + 引用。
- **证据链**：[R9] PlannerTrace 字段骨架；[R29] events/trajectory 时间相位；[R2] 论文 cost 命名；BL-35..38 闭环。
- **弃用**：① 自由格式 payload（字段缺失/混单位）；② hold 伪装新 solve（污染耗时/成功率）。
- **风险**：中。来源——trace 字段不全致无法归因。失效边界——公共必需字段不可缺。验证需求——trace schema 校验。
- **DECOMPOSITION**：✓ 闭环（BL-35..38）。

### DP-15 · 最小闭环仿真验证夹具

- **推荐**：白盒直接调用正式 Adapter；闭环使用唯一 `SimulationSession` + controller + ship model。God 是确定性测试夹具，前端无第二引擎。canonical tuple = `head_on` Viknes/FLSC + `7m/s` + `dt=0.5s` + 无扰动。reference plant 按用途、确定性回归、步长收敛、物理限制验收（不宣称真实船校准）。solve-time 对齐执行前缀；预测误差与 Controller tracking error 分离。
- **证据链**：[R22] Viknes/FLSC plant；[R27] NASA/ITTC/IMO 模型验证（按用途自定验收）；[R33] 多步预测误差监测；BL-39..42 闭环。
- **弃用**：① 第二套简化动力学的假通过；② 点质量/Web 简化引擎与最终 Simulator 不一致；③ 宣称 Viknes digital twin。
- **风险**：中。来源——复用同一模型代码产生循环验证；失配过大把不适用船型误判为算法缺陷。失效边界——MPC 预测模型不被强制等于 plant。验证需求——步长收敛测试 + 隔离阶跃响应。
- **DECOMPOSITION**：✓ 闭环（BL-39..42）。

### DP-16 · 闭环相位与多率关系

- **推荐**：Session 持有唯一 sim clock；同一 `t` 完成环境→sensor→tracker→plan→control，再积分 `t→t+dt`。基础 profile 使用同周期最新 Track、计划当步生效。三态 `MeasurementScan`（`executed=false` / 空扫描 / 有效检测）；每次 scan 带 `sensor_id/scan_id/scheduled_time/capture_time/detections`；每个 Track 带 `state_time/last_detection_time/age`。V1 仅允许 `dt_sim` 整数倍周期（RunSpec 创建时拒绝不兼容）。真实延迟后置。
- **证据链**：[R29] 单步相位；[R30] Radar/KF 扫描周期 + KF 真值初始化泄漏；[R31] VIM Adapter 空扫描语义；BL-43..46 闭环。
- **弃用**：① 浮点取模块私有时钟（漏触发/漂移/重复）；② KF 正式链用 truth 初始化（缺陷）。
- **风险**：中。来源——truth/Tracker/Planner 时间不一致或执行延迟不同致不公平比较。失效边界——统一 sim clock + 整数比周期。验证需求——dt=0.5/0.3/0.7 调度测试。
- **DECOMPOSITION**：✓ 闭环（BL-43..46）。

### DP-17 · MPC 模型与仿真船模失配边界

- **推荐**：V1 冻结 Viknes 3DOF + FLSC 为 canonical synthetic plant；Custom MPC 声明自己的模型。V1 仅 `nominal_reference` profile（不伪造参数扰动）；FCB45 robustness range 保留 EXTERNAL_CONFIRMATION。证据驱动多标签归因：`PLANNER_FAILURE/EXECUTION_FAILURE/MODEL_MISMATCH_SENSITIVITY/SCENARIO_OR_ORACLE_INVALID/UNATTRIBUTED`（缺证据必须 UNATTRIBUTED）。Viknes 结果不得外推 FCB45。
- **证据链**：[R22] Viknes/FLSC 结构（无执行机构动态，crude guessed 风载）；[R23] Telemetron 文献同类但非当前校准；[R32] SB-MPC 结构失配；[R34] 当前无 mismatch profile；BL-47..50 闭环。
- **弃用**：① 复用同一模型代码（循环验证）；② 无惯性运动学 plant（高估转向/制动）；③ 自填 ±10%/±20% 扰动当资格认证。
- **风险**：中。来源——完全一致循环验证；失配过大误判。失效边界——MPC 预测模型 ≠ plant。验证需求——nominal 闭环先量化已存在 prediction/execution gap。
- **DECOMPOSITION**：✓ 闭环（BL-47..50）。

### DP-18 · ENC、环境与终止语义

- **推荐**：同一 ENC source 派生算法/evaluator geometry 并记录 SHA（manifest 增 `enc_hash`）。V1 无风流。物理 collision 只由 truth footprint/sweep 定义（BL-53）；grounding 用 vessel footprint + interval sweep（BL-52）。标准动态场景用 `route_exit`；显式终端状态任务用 `terminal_state`（BL-54）。PSB 风流只作 `source_reproduction`（不伪装 target robustness）。每船独立按静态吃水派生 hazards；只声明 `chart_geometric_clearance`，不宣称 operational UKC。
- **证据链**：[R35][R36][R37] ENC layers + IHO S-57 + IMO A.893；[R38] collision/grounding/goal predicate；[R39] PSB 扰动 corpus；[R51][R52] C²A + Shapely；BL-51..55, BL-65..66 闭环。
- **弃用**：① 单步 Point-in-Polygon（漏船体/扫掠/浅水）；② 中心距当物理碰撞；③ UKC 数值（需潮汐/squat/heel/CATZOC）；④ 复用 ownship hazards 给不同吃水目标船。
- **风险**：高。来源——点船/粗时间步/未知水深漏穿透/船体相交/浅水。失效边界——footprint + sweep + 每船独立 hazards。验证需求——地图 golden geometry 测试 + 窄 hazard 穿越测试。
- **DECOMPOSITION**：✓ 闭环（BL-51..55, BL-65..66）。

### 第二批用户确认门

- 待用户确认 DP-12..18 推荐。
- 建议：批量确认。
- 未确认前不标 VR final，不进 Step5。

### 第二批用户确认 [2026-07-28]

- 用户批量确认 DP-12..18 推荐。
- DP-12..18 标 VR final。
- 技术分解 TD-02 子模块 DP-16..18 全部综合完成。

### DP-19 · 确定性重放

- **推荐**：冻结 episode + SeedBundle + runtime identity。三种重放模式：`artifact playback`（Web 只读六件证据包，不重算算法）、`exact rerun`（runtime fingerprint 相同 + Adapter 声明 exact repeatability probe 通过；episode/调度/identity/状态/事件顺序/规范化数值 exact，不以 Parquet 字节为唯一 oracle）、`tolerance rerun`（native solver 或跨 runtime；离散语义 exact 含 solve/hold 序列/identity/失败状态/碰撞搁浅 COLREG 硬判定；连续数组按字段化 atol/rtol 比较；wall-clock 不参与数值相等）。稳定组件路径 SeedTree（`run_seed → {scenario, sensor/{ship_id}/{sensor_id}, tracker/{ship_id}, disturbance/{wind|current}, algorithm/{ship_id}/{algorithm_id}}`）；路径与 RNG scheme/version 写 manifest；禁止 global/unseeded/shared RNG。runtime fingerprint 进 replay identity（exact 要求相同，tolerance 记录 diff）。PSB/RLMPC native 默认 tolerance-only；同 runtime 重复性 probe 零漂移后才晋级 exact。
- **证据链**：[R40] RunSpec/Manifest/replay/Parquet hash；[R41] RNG 接线；[R42] NumPy NEP 19；[R43][R44] PSB/RLMPC 非确定性；[R45] PyTorch 复现边界；[R46] CRN；[R47] SLSA + numpy.show_runtime；BL-56..60 闭环。
- **弃用**：① 单一根 seed（任一模块新增采样改变其他）；② 全局 RNG/共享 seed（执行顺序影响输入）；③ 以 Parquet 文件字节作唯一数值 oracle；④ tolerance 放宽离散身份/硬 verdict。
- **风险**：高。来源——native/GPU/并行求解器不 bit-exact + 完全不检查无法发现行为漂移。失效边界——硬 verdict 永不放宽。验证需求——exact repeatability probe + tolerance probe。
- **DECOMPOSITION**：✓ 闭环（BL-56..60）。

### DP-20 · MPC 独立评价与资格认证体系

- **推荐**：评价独立于被测 MPC，使用仿真 truth。三层输出：**硬资格门**（证据/身份有效、无 fallback、执行链完成、零 truth collision/grounding/map exit、定向 COLREG 行为 predicate 通过、任务/控制/实时门通过；任一失败即不合格，不得被分数抵消）+ **研究评分**（论文 profile 的 S_safety/S_r/S_theta/S8/S13..17 及 P_*/compensation；用于解释质量和同 profile 比较）+ **诊断**（DCPA/TCPA/footprint clearance/CPA pose/阶段角色/机动起止/路径偏差/控制饱和/solve status/time/iterations/Tracker 误差）。当前 reconstructed evaluator 定级为 `evidence-flow stub`（`numerical_reproduction_confirmed=False`），完成论文公式/profile/golden tables 前不得授予 G3。Multi-ship 先 pairwise 后场景聚合。gate 三态（PASS/FAIL/NOT_EVALUATED）+ qualification 四态（PASS/FAIL/NOT_EVALUATED/INVALID）；全部并发失败保留，primary_reason 仅展示/路由。
- **证据链**：[R1][R2] 独立评价框架；[R48] 当前 reconstructed evaluator 差异（11 项语义未实现）；[R49] 历史 evaluator.yaml；[R50] 2024 grounding extension；BL-61..64 闭环。
- **弃用**：① 单一加权总分决定可用性（碰撞算法因延误小排名高）；② 用 Track 评价（把估计误差当真值）；③ 当前 reconstructed evaluator 授 G3。
- **风险**：高。来源——MPC objective 只证明优化自己目标，不证明安全/守规/可执行。失效边界——硬门独立于评分。验证需求——硬门 predicate 测试 + 论文 golden tables。
- **DECOMPOSITION**：✓ 闭环（BL-61..64）。

### DP-21 · 安全与 ENC Oracle

- **推荐**：`physical_collision`/`physical_grounding` 由 truth footprint + 同步时间连续碰撞检测（C²A conservative advancement）定义；**禁止中心距/CPA/船长半径冒充物理碰撞**，**禁止两船各自独立 swept union 后相交**（须同步时间 A(t)∩B(t)）。`clearance_m` = 两 footprint 最小几何距离（接触后 0）。三类 buffer 分离：numerical tolerance（`set_precision` grid_size << beam）/ chart uncertainty（CATZOC 质量标签非数值 buffer）/ safety buffer（COLREG 安全域）。footprint 用船模 vertex（无 vertex 显式 fallback 五边形）。姿态插值连续（piecewise-constant v/w，screw-motion bounded），不得 lerp 顶点。paper profile 保持固定绝对 CPA（如 ccta_2023_demo 190/100/50/30m）；ship-length-scaled Fujii/Namgung 椭圆船域作独立 profile，缩放后不称论文复现。统一单一 CPA 实现（signed_tcpa/future_cpa/observed_cpa/rel_speed_status），负 TCPA 不自动解除 encounter，低相对速度为工程决策。ENC clearance 四类分离（polygon hazard / point-line distance / unknown-unsurveyed / CATZOC flag），每船独立派生 hazards，不宣称 operational UKC。Simulator/Session/Gym/Evaluator 共用同一 oracle 实现和事件时间语义。
- **证据链**：[R38] collision/grounding predicate；[R51] C²A CCD；[R52][R53] Shapely/set_precision；[R54][R55][R56][R57] ENC layers/CATZOC/ECDIS/S-57；[R58] MSC.192(79) CPA/TCPA 操作员设置；[R59] Namgung CPA/TCPA + Fujii 船域；[R60] COLREG Rule 8；BL-65..69 闭环。
- **弃用**：① 中心距 `<= length/2`；② CPA/安全域改写物理碰撞；③ 两船独立 swept union 相交；④ 三类 buffer 合一；⑤ lerp 顶点；⑥ 论文固定 CPA 缩放后仍称复现；⑦ 负 TCPA 自动解除 encounter；⑧ 点/线 ENC feature buffer 后称真实边界；⑨ operational UKC。
- **风险**：高。来源——点船/粗步/未知水深/独立 union 漏穿透/相交/浅水。失效边界——同步时间 CCD + 三类 buffer 分离 + 每船独立 hazards。验证需求——C²A first-TOC 测试 + 窄 hazard 穿越测试 + grid_size << beam 测试。
- **DECOMPOSITION**：✓ 闭环（BL-65..69）。

### DP-22 · COLREG 行为 Oracle

- **推荐**：truth pairwise Encounter Oracle 锁定规则角色（Eriksen 式 SF↔{OT,HO,GW,SO,EM} FSM，强制 return-to-SF），按风险/阶段解除；算法内部规则状态仅作诊断。oracle 为 profile-parameterized：112.5° crossing/overtaking 边界作 regulatory constant（Rule 21 灯光弧）；head-on 半角与 contact-angle 容差作显式 profile 参数（Woerner 默认 13°/45°/10°）；采用双变量 (β,α) 分类（非 bearing-only）。entry/exit 含 (DCPA,TCPA,t_crit) hysteresis；control state machine 与 evaluation timeline 分离。四阈值 profile（θ_detectable 2°、θ_substantial 30°、Δv_substantial 0.5、t_early_factor range-fraction）。双变量 (α,β) pose；crossing-ahead 经 stand-on 的 α；port-to-port 经 Woerner signed-sine reward；passed-clear 为合取（t_CPA<0 ∧ range increasing ∧ CPA-pose satisfied）。Rule 17 三阶段 sub-FSM（KEEP→MAY_ACT→SHALL_ACT）。multi-ship 不发明优先级（per-pair + C_x,gw compensation）；非合作 = S_* 阈值触发 stand-on MAY_ACT。输出"符合 evaluator profile"，不直接宣称法律合规。
- **证据链**：[R61] COLREGS 条约（仅 22.5° abaft beam 固定）；[R62] Woerner 2016（canonical angles/thresholds/pose reward）；[R63] Woerner 2019；[R64] Eriksen 2020 FSM；[R65][R66] AIS/Akdag 使用 Woerner；[R67] Murray Eq.11；[R68] Zhao DRL；BL-70..74 闭环。
- **弃用**：① 每帧重分类（算法通过自身转向逃离原规则）；② bearing-only 分类；③ range-only stage gate；④ 最终几何证明 Rule 8/16/17 时序行为；⑤ 发明 multi-ship 优先级；⑥ 5°/15° 阈值当论文值（Woerner 2°/30°）。
- **风险**：高。来源——模糊法规术语 + 不锁角色漏错误转向 + 三 A-grade source 给不同角度。失效边界——profile-parameterized + 锁定 FSM。验证需求——论文 golden tables + 双向角色测试 + Rule 17 phase 测试。
- **DECOMPOSITION**：✓ 闭环（BL-70..74）。

### DP-23 · 任务、控制与求解指标

- **推荐**：分任务/执行/求解三组报告，保留原始单位；仅通过安全/COLREG 硬门的 run 参与效率排名。不同算法 objective 不横向比较。`route_exit`/`terminal_state` 双模式 profile 化。tracking error 统一针对闭环执行轨迹（regardless of control form）；控制努力（总舵/总推力）单独报告。`solver.iterations`/`objective` 不横向比较（SQP ≠ CE ≠ DRL）；可比较 wall-clock/feasibility/violation/outcome。collision=FAILED（吸收事件非删失）；timeout=右删失用 Kaplan-Meier + Greenwood；不插补假 arrival；连续指标两种报告（pre-failure prefix OR 完全排除）。deadline：wall-clock + RT-factor 双报告；硬件进 fingerprint。
- **证据链**：[R62] Woerner efficiency/mission metrics + Appendix C RT-factor；[R72] Beiranvand wall-clock 依赖硬件；[R73] Eriksen NLP timing；[R74] Kaplan-Meier；BL-75..79 闭环。
- **弃用**：① 综合分掩盖未到达/饱和/不连续/超时；② 不同 solver objective 横向比较；③ collision 当删失；④ 插补 episode_max；⑤ 单一 wall-clock 无 normalize。
- **风险**：中。来源——平均耗时隐藏 deadline 尾部 + 碰撞后提前终止获虚假低延误。失效边界——分组 + 失败保留分母。验证需求——censoring 测试 + RT-factor 报告。
- **DECOMPOSITION**：✓ 闭环（BL-75..79）。

### DP-24 · G2/G3/G4 证据门

- **推荐**：能力等级按组合证据生成（`capability_profile_id = {rule}:{scenario}:{algorithm}:{tracker}`），不全局硬编码算法等级。G3 canonical set = t=2 covering array（≥16/rule family）× 3 seeds × G3-eligible cells，零硬门失败；G4 保留 `range(30)` + 95% CI。manifest 增 `enc_hash` + 显式 `capability_dependencies` 聚合（失效规则 = 任一成员变化）；变更分类 BREAKING/COMPATIBLE/SUPERSEDED。G3 须零硬门失败；TIMEOUT_FEASIBLE 为 G3 soft gate 非 PASS、G4 失败；NOT_EVALUATED 不能 G3。Web：per-cell matrix + aggregate badge = 最小 grade + evidence drill-down。promotion 需人工审核 + audit trail（approver/tool version）；demotion 自动即时。Nominal 仅作 G2 风险基线。
- **证据链**：[R21] NIST covering-array；[R40] manifest identity；[R48][R49] evaluator stub；[R69][R70][R71] DO-178C/ISO 26262/IEC 61508；[R8] capability matrix；BL-80..84 闭环。
- **弃用**：① 全局硬编码算法等级（随代码/地图/依赖漂移失效）；② import/单次无碰撞当 G3；③ auto-promotion 无人工审核。
- **风险**：高。来源——手工等级不随漂移失效 + auto-promotion 无审核。失效边界——组合证据 + capability_dependencies hash + 人工签 off。验证需求——canonical set 硬门回归 + manifest-diff 失效检查。
- **DECOMPOSITION**：✓ 闭环（BL-80..84）。

### DP-25 · 公平 episode、seed 与统计政策

- **推荐**：G3 用 deterministic canonical set；G4 用预注册 seed + 配对统计。**不硬编码 seed 数**；precision-target on paired difference（~20-50 起始 + sequential addition to declared half-width）。tuning/qualification/holdout 三不相交 + no-look-ahead（G3 属 qualification；evaluator 在 tuning 冻结）。CI 方法：failure-rate→Wilson score（非 Wald）；censored arrival→Kaplan-Meier + Greenwood；paired continuous→paired-t if normal else Wilcoxon signed-rank，bootstrap CI 作 robust default；small canonical n→descriptive + nonparametric CI，formal tests 留 G4。CRN 仅外生输入（keyed-CRN 解耦 call order）；不同步 realized measurement stream（path-dependent visibility 是系统属性）。每 run 持久化 `(n_attempted, n_completed, n_crashed, n_timeout, n_no_output)`；连续 CI 仅 `n_completed`；failure rate Wilson on `n_attempted`；**绝不**插补假 arrival time。所有失败保留分母。
- **证据链**：[R46] Ehrlichman CRN paired framework；[R74] Kaplan-Meier；[R75] Koehler 无固定 replication；[R76] Wilson；[R77] Efron bootstrap；[R78] Wilcoxon；[R79] Little & Rubin MNAR；BL-85..89 闭环。
- **弃用**：① 删除碰撞/超时/crash（幸存者偏差）；② 重复用验证集调参（过拟合）；③ 均值隐藏长尾；④ Wald 区间；⑤ 插补 episode_max；⑥ 强制同步 visibility。
- **风险**：高。来源——统计方法不当致结论不可信。失效边界——配对 + 失败保留 + 正确 CI。验证需求——paired difference CI + Wilson failure rate + KM censoring。
- **DECOMPOSITION**：✓ 闭环（BL-85..89）。

### DP-26 · 可复现实验证据包

- **推荐**：保持 manifest/episode/events/trajectory/evaluation/report 六件包；events/trajectory 增量写，成功/失败均原子封存。trajectory/events 列级 schema + schema_version。events.jsonl 改 append + fsync；manifest/evaluation/report 用 `.tmp` + atomic rename；crash 保留 partial 标志。大 horizon（>1000 步 或 >10 目标）拆 per-solve `{run_id}/solves/{solve_id}.json` + events 引用。内容 hash（canonical JSON SHA-256）+ manifest 签发（`tamper_evident` 非 `tamper_proof`）。V1 不支持 pickle；legacy 仅一次性迁移。Web 只读同一证据。
- **证据链**：[R29] events/trajectory 持久化；[R40] manifest/replay/hash；BL-90..94 闭环。
- **弃用**：① pickle/单体 JSON（不利于审计/迁移/增量写/安全读取）；② 只在正常结束写文件（丢 native crash 证据）。
- **风险**：中。来源——部分写入伪装完整 run。失效边界——增量写 + 原子封存。验证需求——native crash 后证据完整性测试。
- **DECOMPOSITION**：✓ 闭环（BL-90..94）。

### 第三批用户确认门

- 待用户确认 DP-19..26 推荐（8 个 DP，Playground 正确性核心）。
- 建议：逐条或批量确认。
- 未确认前不标 VR final，不进 Step5。

### 第三批用户确认 [2026-07-28]

- 用户批量确认 DP-19..26 推荐。
- DP-19..26 标 VR final。
- 技术分解 TD-03 子模块 DP-21..26 全部综合完成。

### DP-27 · 外部/原生算法隔离 Worker

- **推荐**：按需隔离；兼容算法可 in-process，native/冲突算法使用本地 Worker。V1 subprocess 优先（`multiprocessing` 或 `subprocess.Popen`）；container 仅用于无法共存的依赖 profile（如 RLMPC acados vs PSB Eigen）。V1 每 run 新建 Worker（冷启动，匹配 reset 语义）；持久 Worker 后置（须泄漏 probe 通过）。Worker startup/reset 后清空所有内部状态（warm start/cache/RNG）；replay 用新 Worker + 同 seed + 同 runtime fingerprint。in-process 传完整 ENC；subprocess Worker 传裁剪 hazard geometry（BL-69 四类 + footprint-relevant union）+ bbox + SHA；大 horizon 用共享内存或 memoryview；序列化 MessagePack/Arrow（非 pickle）。本地单用户最小安全：Worker 无网络访问、无文件系统写（除指定 output_dir）、CPU/内存上限（`resource.setrlimit`）；不做鉴权；container profile 加 seccomp/AppArmor。
- **证据链**：[R11] 当前 in-process；[R43] PSB native abort；[R44] RLMPC 依赖冲突；[R35] ENC 加载慢；BL-95..99 闭环。
- **弃用**：① 全部容器化（无谓复杂）；② 完全不隔离（一次崩溃破坏整个服务）；③ 持久 Worker 跨 run（状态泄漏）；④ pickle 跨进程。
- **风险**：中。来源——native abort 连同 Web/Session 退出 + 依赖冲突。失效边界——subprocess 隔离 + 每 run 新建。验证需求——native abort 不影响主进程测试。
- **DECOMPOSITION**：✓ 闭环（BL-95..99）。

### DP-28 · in-process/Worker 边界与运行时身份

- **推荐**：执行模式属 runtime profile，不由算法名硬编码。in-process 准入需 crash/timeout/reset/replay 四 probe 全过（注入异常确认不崩主进程 + 可中断 + 零状态残留 + 同 seed 零漂移），否则 subprocess。lockfile（`uv.lock`/`requirements.txt`）hash 进 manifest；native 依赖（CMake/build flags/binary SHA）进 `AlgorithmDescriptor.build_identity`（缺失标 UNKNOWN）。container profile 记录 image digest + 本地源码 commit + mount 路径；无 digest 标 `unreproducible`。持久 Worker 后置；启用前须泄漏 probe（同 episode 两次 run 比对 horizon/state/RNG 零差异）；V1 不启用。
- **证据链**：[R40] manifest dependencies；[R42] NumPy 跨 build 边界；[R43][R44] PSB/RLMPC native；BL-100..103 闭环。
- **弃用**：① 按算法名硬编码执行模式；② import 成功当 reset/deadline/隔离证明；③ 持久 Worker 无泄漏检测。
- **风险**：中。来源——依赖升级改变 native runtime 后旧 capability 误用。失效边界——四 probe 准入 + build_identity。验证需求——四 probe 测试套件。
- **DECOMPOSITION**：✓ 闭环（BL-100..103）。

### DP-29 · Worker 通信、超时与崩溃语义

- **推荐**：协议版本化，区分 health/reset/plan/shutdown。V1 subprocess 用 stdin/stdout JSON Lines（每行一帧：`{request_id, type, payload}`）；大数组（horizon/ENC）用 base64 Arrow IPC 或共享内存；stderr 留日志（截断保留上限如 1MB，清理敏感占位符）。parent 持有 hard deadline；超时先 `SIGTERM`（grace period 内收集部分响应），再 `SIGKILL`；crash/timeout 使当前正式 run 失败，Worker 仅为下一 run 重建。每 plan 请求唯一 `request_id` + `solve_id`；plan 不自动重试；相同 `request_id` 重复 = 客户端错误；有状态 plan 幂等 = 同 request_id 返回缓存（仅未超时）。V1 每 run 新建；startup health probe。
- **证据链**：[R9] solve_id；[R10] persistence；BL-104..108 闭环。
- **弃用**：① 无 framing JSON（日志污染）；② 只等进程退出（无法中止卡死）；③ 自动重试有状态 plan（重复更新）；④ 自动重启继续 run（丢 warm start）。
- **风险**：中。来源——协议无 framing + 无 hard deadline + 自动重试。失效边界——JSON Lines + SIGTERM→SIGKILL + 不重试。验证需求——超时/崩溃恢复测试。
- **DECOMPOSITION**：✓ 闭环（BL-104..108）。

### DP-30 · 外部 MPC 输出归一化

- **推荐**：每个 Adapter 版本化 `TrajectoryMapping`/`StatusMapping`；先 raw、后归一化，保存两者 hash。PSB：native `(4,N)` `[x,y,chi,U]` col-0=current → public `(9,N)`（`psi:=chi`, `u/v` 待裁决 sin(chi) vs 0, accelerations finite-diff estimated=true）；control `(u_d*u_opt, chi_d+chi_opt)`；native predicted_trajectory 是真实 plant_prediction（正式 `PSBMPCColav` 正确读，legacy wrapper 丢弃自己 roll out）。RLMPC：native `(6,N)` `[x,y,chi,U,V,r]` → public `(9,N)`（`psi:=chi`, `u:=U`, `v:=V`, `r:=r` 故 psi_dot native 无需 finite-diff, accelerations finite-diff）；control `[Fx,Fy]`；reference `nominal_trajectory (6,N)`。method-driven 可验证（atan2/identity, estimated=false/true+method）vs estimated（finite_diff, estimated=true+method+dt）。stock payload 小（PSB~1-4KB 3 字段, RLMPC~5KB 10 keys）+ as-returned 持久化；PSB objective/constraints 须 C++ binding 改动（flag future）。PSB 无 INFEASIBLE 区分（C++ 零 throw/assert，UNKNOWN，统一 NUMERICAL_FAILURE）；RLMPC local enum 映射表（非 upstream acados）；status 须扩展 wrapper 暴露。不能提取真实 horizon/时间网格/所选控制的外部 MPC 最多 G2。
- **证据链**：[R43] PSB 源码（`optimal_offsets_results_py`, `predicted_trajectory`, KinematicShip 构造）；[R44] RLMPC 源码（Viknes model, `plan()` return dict, AcadosErrorCode）；BL-109..113 闭环。
- **弃用**：① `vstack zeros` 隐藏缺失语义；② 单一 exception 丢失 timeout/infeasible 差别；③ 重新生成展示轨迹（脱离真实解）；④ 把 legacy wrapper 的 reference_rollout 当 plant_prediction。
- **风险**：高。来源——维度映射错误 + native status 丢失 + wrapper 不可用。失效边界——版本化 Mapping + as-returned 持久化 + 先修复 wrapper。验证需求——native vs normalized hash 比对 + status 映射测试。
- **冲突标注**：`v` 的处理（PSB `U*sin(chi)` vs `0`）证据分裂——PSB native 假设 course-aligned（v≡0），但 public 契约若要求 body-frame sway 则需裁决。留 Step5 DESIGN-IT-TWICE 解决。
- **DECOMPOSITION**：✓ 闭环（BL-109..113）。

### DP-31 · 后端到 Web Viewer 的只读边界

- **推荐**：后端唯一事实源；WebSocket 是可降采样实时投影，REST/artifacts 是完整证据。Web 消费 Session/PlannerTrace/Evaluator/Evidence 的版本化投影，不重新实现动力学/风险/规则。WebSocket 消息带 `schema_version`；字段演进 additive-only（新增不破坏旧客户端）；删除/重命名 bump major + 兼容窗口。推送频率 = 仿真步降采样（如每 N 步或每 100ms）；背压 = 慢客户端丢中间帧（保留最新）；断连不影响 run；客户端重连用 `seq` 追赶。Web 不发完整 raw horizon/ENC（降采样投影：horizon 前 20 点、ENC bbox outline）；大数据走 REST artifact 下载。本地单用户不做鉴权；绑 `127.0.0.1`；远程后置 token+TLS。live state 带单调 `seq`；Web 消息带 `seq` + 当前 manifest hash；客户端校验 live seq ≤ artifact seq；run 结束后 artifact 为权威，live 不再更新。
- **证据链**：[R10] Session/Evaluator；[R31] Web 只读边界；BL-114..118 闭环。
- **弃用**：① 前端自行计算 CPA/规则标签（与离线报告不同结论）；② 直接发送内部对象（schema 漂移）；③ 每步发全部 raw horizon/ENC（丢帧/UI 卡顿）；④ 慢客户端阻塞仿真。
- **风险**：中。来源——schema 漂移 + 慢客户端阻塞 + 前端重算。失效边界——版本化投影 + 降采样 + 背压。验证需求——断连恢复测试 + schema 兼容测试。
- **DECOMPOSITION**：✓ 闭环（BL-114..118）。

### 第四批用户确认门 + Step4 完成门

- 待用户确认 DP-27..31 推荐（最后 5 个 DP）。
- Step4 完成门检查（design-grounding SKILL）：
  - ✅ 每 DP 有推荐 + 证据 + 弃用（DP-05..31 共 27 项全部综合）。
  - ✅ 技术分解无遗漏（TD-01..04 全部子模块综合完成；无 DECOMPOSITION_INCOMPLETE）。
  - ✅ 推荐有风险量化 + 失效边界 + 验证需求。
  - ✅ 冲突标注（DP-30 `v` 处理证据分裂，留 Step5）。
- 未确认前不标 VR final，不进 Step5。

### 第四批用户确认 + Step4 完成 [2026-07-28]

- 用户批量确认 DP-27..31 推荐。
- DP-27..31 标 VR final（VR-27..31）。
- 技术分解 TD-04 子模块 DP-28..30 全部综合完成。
- **Step4 完成**：DP-05..31 共 27 项全部综合，VR-05..31 登记；TD-01..04 无 DECOMPOSITION_INCOMPLETE；冲突标注 DP-30 `v` 留 Step5。
- 不自动进入 Step5；等待用户授权。

#### Step4 完整 MPC Playground 方案概览

**一、平台定位（VR-01..04）**
- 一条动态 MPC 避碰验证主链；论文复现/RRT/VIM 为条件插件；`Custom MPC` = 用户自研 MPC 经统一 Adapter 接入。

**二、输入边界（VR-05..11）**
- 场景：当前五类标准场景 + PSB 小型固定迁移样本（三件套）。
- ODD：V1 四类双船 open-water + God + Viknes + 无风流。
- 资格顺序：Nominal→VO/SB→Custom→PSB/RL 条件。
- 接口：`CustomMPCAdapter(ICOLAV)` + typed `PlannerInput` DTO + `AlgorithmDescriptor`（12 强制字段）。
- 输入语义：Adapter 验证坐标/单位/age/PSD/shape；缺失→INVALID_INPUT。
- 输出语义：`9xN` col-0=solve-time；StateMapping 版本化；连续性检查。

**三、执行与诊断（VR-12..14）**
- 时序：多率调度；solve 在 t=0；hold 保留 horizon 原点；离线可关 deadline。
- 失败：strict_no_fallback；六态分类；TIMEOUT_FEASIBLE 计 deadline；归因三源。
- 诊断：真实 solve 才写 events；公共 9+专项 4 字段；多模态 target schema；大 horizon 拆文件。

**四、仿真夹具（VR-15..18）**
- 夹具：白盒+闭环走同 Adapter；canonical Viknes tuple；reference plant 按用途验收。
- 相位：统一 sim clock；三态 MeasurementScan；V1 整数比周期。
- 失配：nominal_reference 不伪造扰动；多标签归因；不外推 FCB45。
- 环境：同 ENC + enc_hash；footprint+sweep；route_exit/terminal_state；每船独立 hazards；只 chart_geometric_clearance。

**五、重放与身份（VR-19）**
- 三模式（artifact playback/exact/tolerance）；SeedTree 稳定路径；runtime fingerprint；native 默认 tolerance-only。

**六、独立评价（VR-20..26）**
- 三层分离：硬资格门 / 论文评分 / 诊断；score 不抵消硬失败。
- 安全 oracle：footprint+同步 CCD 定义 collision/grounding；三类 buffer 分离；统一 CPA；ENC 四类分离。
- COLREG oracle：profile-parameterized；锁定 FSM；双变量(β,α)；四阈值；Rule 17 三阶段。
- 指标：任务/执行/求解三组；objective 不横向比较；RT-factor 双报告。
- 资格：组合证据；canonical=t=2 covering×3 seeds×零硬门；promotion 人工+demotion 自动。
- 统计：不硬编码 seed；Wilson/KM/paired-t/Wilcoxon/bootstrap；绝不插补。
- 证据包：六件包；增量写+原子封存；tamper_evident。

**七、外部算法 Worker（VR-27..30）**
- 隔离：subprocess 优先；每 run 新建；四 probe 准入。
- 通信：JSON Lines；SIGTERM→SIGKILL；不重试。
- 归一化：版本化 TrajectoryMapping/StatusMapping；PSB(4,N) plant_prediction；RLMPC(6,N) r=psi_dot。

**八、Web 只读边界（VR-31）**
- 版本化投影；降采样推送；不发 raw；127.0.0.1；live seq+hash。

**已知冲突（留 Step5）**：DP-30 PSB `v` 处理（sin(chi) vs 0）。

**诚实边界（EXTERNAL_CONFIRMATION_REQUIRED）**：FCB45 目标 plant、CATZOC 数值精度表、目标海域 metocean、Agder 地图、历史许可。

**实现期须修复的代码缺陷**（15+ 项）：中心距碰撞、五边形 footprint、RK4 无 dense output、三套 CPA 不一致、ENC 中心点距离、删除 Polygon interior、grunne 点喂入 seabed、shore 折叠 UNSARE、bearing-only 分类、range-only stage、evaluator 5°/15° 偏差、无 Rule 17 FSM、KinematicShip 参数误绑、AcadosMPCWrapper 不可用、grounding oracle 调不存在函数。

## Step5 · DESIGN-IT-TWICE 方案对比 [2026-07-28]

### 用户授权 + 对比对象

- 用户授权 7 项进 DESIGN-IT-TWICE：5 项核心（DP-08/21/22/24/30）+ 2 项边界（DP-19/25）。
- 20 项低风险直接采纳 Step4 推荐（用户确认）。
- 输出：每项 2-3 竞争方案 + 决策卡片（七维）+ 裁决。分两批展示。

### DP-08 · 统一 Custom MPC 插件契约

#### 方案 A：薄 Adapter over ICOLAV（Step4 推荐）

| 维度 | 方案 A：薄 Adapter over ICOLAV |
|---|---|
| 来源 | [R3] ICOLAV 稳定边界；[R9] PlannerTrace 骨架；[R11] legacy adapter 反面教材 |
| 工程验证 | 上游 COLAV-Simulator 生产✓（VOWrapper/SBMPCWrapper/PSBMPCColav 均实现 ICOLAV）|
| 技术分解 | 输入✓（typed PlannerInput DTO）输出✓（9xN+selected_command）声明✓（AlgorithmDescriptor）生命周期✓（reset/solve_id）失败✓（PlanStatus 六态）诊断✓（PlannerTrace）|
| 失效边界 | Adapter 验证不完整时"求解成功但物理错误"（SC-01 白盒注入无效输入可证）|
| 实现风险 | 低（复用既有 ICOLAV + diagnostics 骨架，增量加 DTO/Descriptor）|
| 可测性 | SC-01 白盒固定输入 + 闭环走同 Adapter（BL-41 已确认）|
| 推荐度 | ★★★★★ |

#### 方案 B：新独立接口（替代 ICOLAV）

| 维度 | 方案 B：新独立接口 |
|---|---|
| 来源 | 无直接证据（推论：clean-slate 设计更纯粹）|
| 工程验证 | 仅本项目✗（须重写 VOWrapper/SBMPCWrapper/PSBMPCColav 全部 wrapper）|
| 技术分解 | 输入✓ 输出✓ 声明✓ 生命周期✓ 失败✓ 诊断✓（理论上完整）|
| 失效边界 | 同 A，但额外引入迁移风险（既有 wrapper 全部重写）|
| 实现风险 | 高（重写 3+ wrapper + 破坏上游兼容 + 双接口维护期）|
| 可测性 | 同 A，但须额外 wrapper 迁移测试 |
| 推荐度 | ★★☆☆☆ |

#### 方案 C：hybrid（ICOLAV 兼容 + Custom 专用 fast-path）

| 维度 | 方案 C：hybrid |
|---|---|
| 来源 | 推论（兼顾兼容与性能）|
| 工程验证 | 仅本项目✗ |
| 技术分解 | 同 A，但额外维护 fast-path（双代码路径）|
| 失效边界 | fast-path 与 ICOLAV 路径行为分叉（两套验证/转换须保持一致）|
| 实现风险 | 中-高（双路径维护 + 一致性测试负担）|
| 可测性 | 须证明两路径行为等价（额外等价性测试）|
| 推荐度 | ★★☆☆☆ |

#### 裁决

- **采纳方案 A**。理由：①技术分解完整且复用既有骨架；②工程验证最强（上游生产 wrapper 均实现 ICOLAV）；③实现风险最低；④失效边界已知可测（SC-01）。
- **弃用 B**：重写全部 wrapper + 破坏上游兼容，无证据收益。
- **弃用 C**：双路径一致性维护负担，fast-path 收益未证。
- 裁决标准：工程验证（生产✓ > 仅本项目✗）+ 实现风险（低 > 高）。
- VR-08 维持（Step4 推荐）。

### DP-21 · 安全与 ENC Oracle

#### 方案 A：C²A Conservative Advancement 循环（Step4 推荐）

| 维度 | 方案 A：C²A CA 循环 |
|---|---|
| 来源 | [R51] Tang C²A ICRA 2009（CCD 奠基）；[R52][R53] Shapely manual/set_precision |
| 工程验证 | C²A 在机器人/游戏 CCD 生产✓；Shapely 广泛生产✓；海事 footprint CCD 仅本项目 |
| 技术分解 | footprint✓（船模 vertex）姿态插值✓（piecewise-constant v/w screw-motion）first-TOC✓（Eq.1-2）容差✓（user-specified threshold）三类 buffer 分离✓ ENC 四类分离✓ |
| 失效边界 | dt 过大 + ROT 高时 CA 步数多（性能）；grid_size ≥ beam 时拓扑坍缩（SC-07 受限水域窄 hazard）|
| 实现风险 | 中（C²A CA 循环 + Shapely 调用；性能须测）|
| 可测性 | SC-07 窄 hazard 穿越测试 + first-TOC 已知解比对 + grid_size<<beam 测试 |
| 推荐度 | ★★★★★ |

#### 方案 B：自适应姿态细分（subdivide until safe）

| 维度 | 方案 B：自适应姿态细分 |
|---|---|
| 来源 | [R51] C²A 动机上界思想的简化实现；工程推论 |
| 工程验证 | 仅本项目✗（简化版 CCD 常见但无海事生产先例）|
| 技术分解 | footprint✓ 姿态细分✓（递归二分到步长安全）first-TOC✗（只判是否碰撞，不给 first-TOC）容差✓ 三类分离✓ ENC✓ |
| 失效边界 | 细分收敛依赖运动上界估计；估计偏松则过保守（性能差），偏紧则漏报 |
| 实现风险 | 中（比 A 简单，但无 first-TOC）|
| 可测性 | SC-07 穿越测试；但无法提供 first-TOC 供 Evaluator 用 |
| 推荐度 | ★★★☆☆ |

#### 方案 C：简化线性上界（max vertex displacement check）

| 维度 | 方案 C：简化线性上界 |
|---|---|
| 来源 | 工程推论（最快实现）|
| 工程验证 | 仅本项目✗ |
| 技术分解 | footprint✓ 上界✓（(|v|+|w|·r_max)·dt）first-TOC✗ 容差✗（无精细化）三类分离✓ ENC✓ |
| 失效边界 | 旋转下严重过保守（球体包围）；或若忽略旋转项则漏报 |
| 实现风险 | 低（最简实现）|
| 可测性 | SC-07；但过保守会误报（影响评价公正性）|
| 推荐度 | ★★☆☆☆ |

#### 裁决

- **采纳方案 A**。理由：①first-TOC 是 Evaluator 需要的（碰撞时间供阶段/时序评价）；②工程验证最强（C²A + Shapely 生产级）；③三类 buffer + ENC 四类分离完整；④失效边界已知（dt/ROT/grid_size）。
- **弃用 B**：无 first-TOC，Evaluator 缺关键信号。
- **弃用 C**：过保守误报影响公正性 / 漏报风险。
- VR-21 维持。

### DP-22 · COLREG 行为 Oracle

#### 方案 A：Woerner 全套 + Eriksen 锁定 FSM（Step4 推荐）

| 维度 | 方案 A：Woerner 全套 + Eriksen FSM |
|---|---|
| 来源 | [R62] Woerner 2016 MIT PhD（canonical angles 13°/45°/10° + Algorithm 5/9/11/12/14/16 + pose reward Eq.4.12）；[R64] Eriksen 2020 FSM（SF↔{OT,HO,GW,SO,EM} + hysteresis）|
| 工程验证 | Woerner MIT 论文 + Autonomous Robots✓；Eriksen NTNU 论文✓；[R65][R66] Hagen/Akdag 引用 Woerner✓；海事生产✗（研究级）|
| 技术分解 | 分类✓（双变量 β,α）阶段✓（Stage 1-4 + FSM lock）阈值✓（四阈值 profile）通过侧✓（signed-sine pose）Rule 17✓（三阶段 sub-FSM）multi-ship✓（per-pair + C_x,gw）|
| 失效边界 | profile 参数选择影响结果（SC-02..06 须声明 profile）；FSM hysteresis 阈值未确认 Hagen 值 |
| 实现风险 | 中-高（双变量分类 + FSM + pose reward + Rule 17 sub-FSM；工作量大）|
| 可测性 | 论文 golden tables（Woerner Road Test Tables 7.1/7.2）+ 双向角色测试 + Rule 17 phase 测试 |
| 推荐度 | ★★★★★ |

#### 方案 B：Eriksen FSM + 宽角度（Tam&Bucknall 22.5°）

| 维度 | 方案 B：Eriksen FSM + 宽角度 |
|---|---|
| 来源 | [R64] Eriksen 2020（FSM + θ₁,θ₂,θ₃=22.5/90/112.5° + Tam&Bucknall robustness）|
| 工程验证 | Eriksen 论文✓；但未含 Woerner pose reward / crossing-ahead α / Algorithm 12 timely |
| 技术分解 | 分类✓（单变量 bearing）阶段✓ 阈量✗（缺 timely range-fraction）通过侧✗（无 signed-sine）Rule 17✓ multi-ship✓ |
| 失效边界 | bearing-only 漏 contact-angle 区分；无 pose reward 无法判 port-to-port 质量 |
| 实现风险 | 中（比 A 简单，但缺关键子模块）|
| 可测性 | Eriksen 场景测试；但无法复现 Woerner golden tables |
| 推荐度 | ★★★☆☆ |

#### 方案 C：Murray 窄角度（5°）简化版

| 维度 | 方案 C：Murray 简化版 |
|---|---|
| 来源 | [R67] Murray & Naeem 2024（Eq.11 HO ±5°）|
| 工程验证 | arXiv preprint（B 级）；无 FSM / pose / Rule 17 |
| 技术分解 | 分类✓（单变量）阶段✗ 阈值✗ 通过侧✗ Rule 17✗ multi-ship✗ |
| 失效边界 | 缺阶段锁定/通过侧/Rule 17——大量 COLREG 评价缺失 |
| 实现风险 | 低（最简）|
| 可测性 | 仅分类测试 |
| 推荐度 | ★☆☆☆☆ |

#### 裁决

- **采纳方案 A**。理由：①技术分解最完整（六子模块全覆盖）；②canonical 来源（Woerner + Eriksen 被 Hagen/Akdag 引用）；③双变量分类 + pose reward + Rule 17 sub-FSM 是 paper_compatible profile 必需；④失效边界已知（profile 参数）。
- **弃用 B**：缺 timely/pose/crossing-ahead，技术分解不完整。
- **弃用 C**：残缺方案（仅分类），直接弃用（裁决标准 1：技术分解完整性）。
- VR-22 维持。

### 第一批决策卡片用户确认门

- 待用户确认 DP-08（采纳 A）、DP-21（采纳 A）、DP-22（采纳 A）的裁决。
- 未确认前不标 final，不继续后 4 项。

### 第一批用户确认 [2026-07-28]

- 用户批量采纳 DP-08 方案 A、DP-21 方案 A、DP-22 方案 A。
- VR-08/21/22 经 DESIGN-IT-TWICE 确认，维持 Step4 推荐。
- 弃用方案登记：ALT-05（DP-08 B/C）、ALT-06（DP-21 B/C）、ALT-07（DP-22 B/C）。

### DP-24 · G2/G3/G4 资格门与 canonical set

#### 方案 A：t=2 Covering Array + 多 seed + 零硬门（Step4 推荐）

| 维度 | 方案 A：t=2 covering array + 3 seeds + 零硬门 |
|---|---|
| 来源 | [R21] NIST SP 800-142 covering-array；[R40] manifest identity；[R48][R49] evaluator stub；[R8] capability matrix |
| 工程验证 | NIST ACTS 方法论生产✓（软件测试）；[R69][R70][R71] 安全标准 V&V 原则✓；海事 G3 canonical 仅本项目 |
| 技术分解 | canonical set✓（covering array）零失败✓（硬门 PASS）capability_dependencies✓（hash 聚合）TIMEOUT_FEASIBLE✓（soft）promotion✓（人工+audit）demotion✓（自动）|
| 失效边界 | t=2 漏 t=3 交互故障（可通过升级 t=3 缓解）；seed=3 统计功效低（G4 用 range(30) 补）|
| 实现风险 | 中（covering array 生成 + 硬门 predicate + manifest-diff 失效检查）|
| 可测性 | canonical set 硬门回归 + capability_dependencies hash 比对 + promotion/demotion 流程测试 |
| 推荐度 | ★★★★★ |

#### 方案 B：全量 PSB benchmark（每 stratum 100）

| 维度 | 方案 B：全量 PSB benchmark |
|---|---|
| 来源 | [R19][R20] PSB corpus（3600 episode，每 stratum 100）|
| 工程验证 | PSB benchmark✓（上游忠实运行语义）；但 schema 不兼容（BL-01 迁移）+ Agder 缺失（BL-02）|
| 技术分解 | canonical set✓（全量）零失败✓ dependencies✓ TIMEOUT_FEASIBLE✓ promotion✓ demotion✓ |
| 失效边界 | 运行成本高（3600×算法×seed）；schema 迁移风险；地理覆盖偏 PSB corpus |
| 实现风险 | 高（迁移 + 大量运行 + 长周期）|
| 可测性 | 同 A，但运行预算大 |
| 推荐度 | ★★☆☆☆ |

#### 方案 C：缩减固定集（经验选 N，无 covering-array 论证）

| 维度 | 方案 C：缩减固定集 |
|---|---|
| 来源 | 无方法论支撑（经验拍 N）|
| 工程验证 | 仅本项目✗ |
| 技术分解 | canonical set✗（无覆盖强度论证）零失败✓ dependencies✓ TIMEOUT_FEASIBLE✓ promotion✓ demotion✓ |
| 失效边界 | 覆盖不可量化；新增 factor 不知是否破坏覆盖 |
| 实现风险 | 低（最少 episode）|
| 可测性 | 无法证明覆盖强度 |
| 推荐度 | ★☆☆☆☆ |

#### 裁决

- **采纳方案 A**。理由：①覆盖强度可量化（NIST 方法论）；②实现风险中（vs B 高）；③运行成本可控（vs B 3600）；④失效边界已知（t=2 限制可升级）。
- **弃用 B**：运行成本高 + schema 迁移风险 + 地理偏 PSB corpus。
- **弃用 C**：无覆盖论证（裁决标准 1：技术分解完整性，canonical set 子模块残缺）。
- VR-24 维持。

### DP-30 · 外部 MPC 输出归一化（含 PSB `v` 冲突解决）

#### 冲突回顾

Step4 标注：PSB native `[x,y,chi,U]` → public 9D 时，`v`（body-frame sway）处理证据分裂：
- 选项 1：`v := U*sin(chi)`（body-frame 速度分解）
- 选项 2：`v := 0`（PSB native 假设 course-aligned，sway 恒零）

#### 方案 A：method-driven 映射 + `v:=0` 标 native_assumption（Step4 推荐 + 冲突解决）

| 维度 | 方案 A：method-driven + v:=0 native_assumption |
|---|---|
| 来源 | [R43] PSB `kinematic_ship_models_cpu.cpp:477-489`（single-integrator course/speed，v≡0 是 native 假设）；[R44] RLMPC Viknes `[U,V,r]`（V native 存在）；BL-111 method-driven |
| 工程验证 | PSB/RLMPC 源码 verbatim✓；TrajectoryMapping 版本化是工程实践 |
| 技术分解 | PSB 映射✓ RLMPC 映射✓ 可验证推导✓（atan2/identity）estimated 推导✓（finite_diff）stock payload✓ status 映射✓ `v` 冲突解决✓ |
| 失效边界 | PSB 无 INFEASIBLE 区分（UNKNOWN）；wrapper 须先修复（KinematicShip 参数误绑 + AcadosMPCWrapper）；`v:=0` 与 body-frame 评价若有冲突需 profile 声明 |
| 实现风险 | 中（映射 + wrapper 修复 + status 暴露）|
| 可测性 | native vs normalized hash 比对 + status 映射测试 + PSB `v:=0` 标记审计 |
| 推荐度 | ★★★★★ |

**`v` 冲突解决**：采用 `v := 0` + `estimated=false, method="native_assumption_course_aligned"`。理由：PSB native 动力学（`xs_new(0)=xs_old(0)+dt*xs_old(3)*cos(xs_old(2))`）是 single-integrator course/speed 模型，**sway 恒零是 native 假设而非遗漏**（[R43] verbatim）。若强行 `v:=U*sin(chi)` 会引入 native 不存在的 sway 速度，污染 PSB 预测语义。RLMPC 则 `v:=V`（native 存在，无需处理）。`TrajectoryMapping` 版本化记录此差异；若未来 body-frame 评价要求非零 sway，标 profile 冲突回炉。

#### 方案 B：统一 `v := U*sin(chi)`（所有 course-speed 模型）

| 维度 | 方案 B：统一 v:=U*sin(chi) |
|---|---|
| 来源 | 推论（统一 body-frame 分解）|
| 工程验证 | 仅本项目✗ |
| 技术分解 | PSB 映射✓ RLMPC 映射✓（但 V 已 native，sin(chi) 多余）推导✓ payload✓ status✓ `v`✗（引入 native 不存在的 sway）|
| 失效边界 | PSB 预测被注入虚拟 sway，污染 plant_prediction 语义；与 BL-42 标记冲突（reference_rollout vs plant_prediction 混淆）|
| 实现风险 | 中 |
| 可测性 | 难以验证"虚拟 sway"是否合理 |
| 推荐度 | ★★☆☆☆ |

#### 方案 C：PSB 不映射到 9D（保留 native 4D，标 G2 上限）

| 维度 | 方案 C：PSB 保留 native 4D |
|---|---|
| 来源 | [R43] PSB native 4D；BL-30"不能提取真实 horizon 的外部 MPC 最多 G2" |
| 工程验证 | 诚实但放弃 G3 资格 |
| 技术分解 | PSB 映射✗（不映射）RLMPC✓ 推导✗ payload✓ status✓ `v`✓（回避）|
| 失效边界 | PSB 永远 G2（无法与其他算法 G3 比较）|
| 实现风险 | 低（不映射）|
| 可测性 | — |
| 推荐度 | ★★☆☆☆ |

#### 裁决

- **采纳方案 A**。理由：①尊重 native 语义（v≡0 是 PSB 假设）；②method-driven 区分可验证/estimated/native_assumption；③PSB 可达 G3（vs C 永远 G2）；④`v` 冲突显式解决并记录。
- **弃用 B**：注入 native 不存在的虚拟 sway，污染 plant_prediction。
- **弃用 C**：PSB 永远 G2，无法公平比较。
- **冲突解决**：`v := 0` + `method="native_assumption_course_aligned"`，`estimated=false`；RLMPC `v := V` native。TrajectoryMapping 版本化。
- VR-30 维持（Step4 推荐 + 冲突解决）。

### DP-19 · 确定性重放

#### 方案 A：三模式（playback/exact/tolerance）+ SeedTree + fingerprint（Step4 推荐）

| 维度 | 方案 A：三模式 + SeedTree + fingerprint |
|---|---|
| 来源 | [R40] RunSpec/Manifest/replay；[R42] NumPy NEP 19；[R43][R44] native 非确定；[R46] CRN；[R47] SLSA + numpy.show_runtime |
| 工程验证 | artifact playback（Web 只读）✓；exact/tolerance 区分是仿真复现实践✓；SeedTree 稳定路径是 NumPy 推荐✓ |
| 技术分解 | playback✓ exact✓（fingerprint 相同 + probe）tolerance✓（字段化 atol/rtol，硬 verdict 不放宽）SeedTree✓（稳定路径）fingerprint✓（runtime identity）native policy✓（tolerance-only 默认）|
| 失效边界 | exact 要求 fingerprint 相同（跨 OS/CPU/LAPACK 不可）；tolerance 的 atol/rtol 须来自重复试验非统一常数 |
| 实现风险 | 中（三模式 + probe + fingerprint 采集）|
| 可测性 | exact repeatability probe + tolerance probe + fingerprint diff 报告 |
| 推荐度 | ★★★★★ |

#### 方案 B：单一 file-hash replay（当前实现）

| 维度 | 方案 B：单一 file-hash |
|---|---|
| 来源 | [R40] 当前 trajectory.parquet SHA-256 |
| 工程验证 | 当前实现✓；但 BL-56 已确认混合数值+编码 |
| 技术分解 | playback✗（无分离）exact✗（file-hash 含编码噪声）tolerance✗ SeedTree✗ fingerprint✗ |
| 失效边界 | Pandas/PyArrow 升级致 file-hash 变化但数值未变（假阴性）；或数值变但编码巧合不变（假阳性）|
| 实现风险 | 低（当前已有）|
| 可测性 | 无法定位哪个状态/指令漂移 |
| 推荐度 | ★☆☆☆☆ |

#### 方案 C：全 exact（要求所有 run bit-exact）

| 维度 | 方案 C：全 exact |
|---|---|
| 来源 | 推论（最严格）|
| 工程验证 | 仅同 runtime 可行；[R42] NumPy 明确跨 build 不可 |
| 技术分解 | exact✓ 但 native 不可达 |
| 失效边界 | native solver（PSB/RLMPC）跨 runtime 不 bit-exact → 大量 run 无法 replay |
| 实现风险 | 高（强制不可达的目标）|
| 可测性 | — |
| 推荐度 | ★☆☆☆☆ |

#### 裁决

- **采纳方案 A**。理由：①三模式覆盖所有场景（Web 只读 / 同 runtime / 跨 runtime）；②SeedTree 稳定路径防新增组件改变旧 seed；③硬 verdict 永不放宽；④失效边界已知（fingerprint + atol/rtol 来源）。
- **弃用 B**：file-hash 混合编码噪声，无法定位漂移。
- **弃用 C**：native 不可 bit-exact，强制不可达。
- VR-19 维持。

### DP-25 · 公平 episode、seed 与统计政策

#### 方案 A：precision-target + 配对 + 正确 CI + 不插补（Step4 推荐）

| 维度 | 方案 A：precision-target + 配对 + 正确 CI |
|---|---|
| 来源 | [R46] Ehrlichman CRN paired framework；[R74] Kaplan-Meier；[R75] Koehler 无固定 replication；[R76] Wilson；[R77] Efron bootstrap；[R78] Wilcoxon；[R79] Little & Rubin MNAR |
| 工程验证 | 统计方法全是 primary 奠基✓；配对仿真是仿真比较标准实践✓ |
| 技术分解 | seed✓（precision-target）split✓（三不相交）CI✓（Wilson/KM/t/Wilcoxon/bootstrap）CRN✓（仅外生）missing✓（MNAR 不插补）failure✓（保留分母）|
| 失效边界 | precision-target 须 pilot 估计方差；CRN 仅缩减外生方差非消除系统差异；小 n CI 宽 |
| 实现风险 | 中（precision-target + 多 CI 方法 + 持久化 n_attempted/completed）|
| 可测性 | paired difference CI + Wilson failure rate + KM censoring + MNAR 审计（无插补）|
| 推荐度 | ★★★★★ |

#### 方案 B：固定 30 seed + Wald CI + 完整案例（当前 BatchRunner 实现）

| 维度 | 方案 B：固定 30 + Wald + 完整案例 |
|---|---|
| 来源 | [R48] 当前 BatchRunner（range(30) + 95% CI mean±1.96std/√n）|
| 工程验证 | 当前实现✓；但 [R75] 明确无通用固定数；[R76] Wald 小 n 近 0/1 失败 |
| 技术分解 | seed✗（固定无论证）split✗ CI✗（Wald 不适用小 n）CRN✗ missing✗（complete-case "generally inappropriate"）failure✗（丢弃）|
| 失效边界 | 固定 30 无功效论证；Wald 近 0 crash rate 失败；丢弃 crash 致幸存者偏差 |
| 实现风险 | 低（当前已有）|
| 可测性 | 结论不可信（统计方法缺陷）|
| 推荐度 | ★☆☆☆☆ |

#### 方案 C：纯描述性（无 CI，只报告 mean/std）

| 维度 | 方案 C：纯描述性 |
|---|---|
| 来源 | 推论（最保守）|
| 工程验证 | 仅本项目✗ |
| 技术分解 | seed✗ split✗ CI✗ CRN✗ missing✓（不插补）failure✓ |
| 失效边界 | 无法量化不确定性；无法做配对比较 |
| 实现风险 | 低 |
| 可测性 | 无法统计判别 |
| 推荐度 | ★★☆☆☆ |

#### 裁决

- **采纳方案 A**。理由：①统计方法全是 primary 奠基；②不插补 + 不丢弃是 [R79] MNAR 要求；③CI 方法正确（Wilson/KM 非 Wald）；④配对比较是仿真标准。
- **弃用 B**：固定 seed 无论证 + Wald 失败 + complete-case 幸存者偏差。
- **弃用 C**：无法量化不确定性/做配对比较。
- VR-25 维持。

### 第二批决策卡片用户确认门 + Step5 完成门

- 待用户确认 DP-24（采纳 A）、DP-30（采纳 A + `v` 冲突解决）、DP-19（采纳 A）、DP-25（采纳 A）的裁决。
- Step5 完成门检查（design-grounding SKILL）：
  - ✅ 7 项关键决策点经 DESIGN-IT-TWICE（DP-08/19/21/22/24/25/30）。
  - ✅ 20 项低风险经用户授权直接采纳 Step4 推荐。
  - ✅ 每张决策卡片七维全填。
  - ✅ 裁决有证据链理由，弃用方案有明确弃用理由。
  - ✅ DP-30 `v` 冲突经 DESIGN-IT-TWICE 解决（`v:=0` native_assumption）。
- 未确认前不标 final，不进 Step6。

### 第二批用户确认 + Step5 完成 [2026-07-28]

- 用户批量采纳 DP-24 方案 A、DP-30 方案 A（含 `v` 冲突解决）、DP-19 方案 A、DP-25 方案 A。
- VR-19/24/25/30 经 DESIGN-IT-TWICE 确认，维持 Step4 推荐。
- 弃用方案登记：ALT-08（DP-24 B/C）、ALT-09（DP-30 B/C）、ALT-10（DP-19 B/C）、ALT-11（DP-25 B/C）。
- **Step5 完成**：7 项关键 DP 经 DESIGN-IT-TWICE；20 项低风险用户授权采纳；DP-30 `v` 冲突解决。
- 不自动进入 Step6；等待用户授权。

## Step6 · 术语表 + 技术规约表 + 方案包 [2026-07-28]

### 用户授权

- 用户授权进入 Step6，产出可交付 brainstorming 的完整方案包。

### 1. 术语表

| 术语 | 定义（权威来源）| 本方案具体含义 | 边界（它**不是**什么）| 关联 DP |
|---|---|---|---|---|
| Custom MPC | 用户自研 MPC（VR-04）| 经 `CustomMPCAdapter(ICOLAV)` 接入的避碰算法 | 不是 legacy guidance adapter；不是 SB-MPC/PSB/RLMPC | DP-04,08 |
| `9xN` trajectory | `[x,y,psi,u,v,r,x_ddot,y_ddot,psi_dot]` vstacked（[R3]）| 公共输出契约；col-0=solve-time 当前状态 | 不是 raw native state（PSB 4D / RLMPC 6D 须映射）| DP-10,30 |
| physical_collision | truth footprint 在同步时间 CCD 下相交/接触（[R51]）| 事实事件，不加 buffer | 不是中心距；不是 CPA；不是 safety domain 违反 | DP-21 |
| physical_grounding | truth footprint 与该船 hazards 相交/接触（[R38]）| 事实事件，footprint+sweep | 不是中心点到 hazard 距离；不是 operational UKC | DP-18,21 |
| chart_geometric_clearance | ENC 深度区间多边形 hazard 的几何 clearance（[R54][R57]）| V1 synthetic oracle | 不是 operational UKC（需潮汐/squat/heel）| DP-18,21,69 |
| C²A CCD | Continuous Collision Detection via Conservative Advancement（[R51]）| 同步时间 first-TOC 实现 | 不是端点采样；不是独立 swept union 相交 | DP-21 |
| paper_compatible profile | 复现论文固定参数的 evaluator profile | ccta_2023_demo（190/100/50/30m）+ Woerner 角度 | 不是法规硬事实；缩放后不称复现 | DP-20,22,67 |
| ship-length-scaled profile | Fujii/Namgung 椭圆船域（a·L, b·L）| 独立风险指标 profile | 不替换 paper profile | DP-21,67 |
| G3 | 可观察避碰能力 + 完整诊断 + canonical set 零硬门失败 | 组合证据（rule:scenario:algorithm:tracker）| 不是全局算法等级；不是 import 成功 | DP-24 |
| canonical set | t=2 covering array × 3 seeds × G3-eligible cells | 本项目新建 regression set | 不是 PSB 全量 benchmark；不是经验拍 N | DP-24 |
| SeedTree | 稳定组件路径派生的独立 RNG 流（[R42]）| `run_seed → {scenario, sensor/..., tracker/..., disturbance/..., algorithm/...}` | 不是单一根 seed；不是全局 RNG | DP-19 |
| keyed CRN | 稳定 key 生成外生随机 draw 的 CRN 实例化（[R46]）| 解耦 call order，隔离算法效应 | 不同步 realized measurement stream | DP-19,25 |
| capability_dependencies | capability claim 依赖的 hash 聚合 | `[code_commit, dependencies, scenario_hash, enc_hash, evaluator_id, tracker, plant, runtime_fingerprint]` | 不是普通备注；任一变化即失效 | DP-24 |
| MNAR | Missing Not At Random（[R79]）| crash/timeout 的 missingness 由算法不稳定性驱动 | 不是 MCAR；不可丢弃/插补 | DP-25,89 |
| TIMEOUT_FEASIBLE | solver 返回可行解但超 deadline（[R9]）| G3 soft gate 非 PASS；G4 失败 | 不是 SUCCESS；不是 hold | DP-13,82 |
| TrajectoryMapping | 版本化的 native→public state 映射 adapter | PSB 4D→9D / RLMPC 6D→9D | 不是 vstack zeros；不是重生成轨迹 | DP-30 |
| native_assumption_course_aligned | PSB native 假设 v≡0 | `v:=0, estimated=false, method="native_assumption_course_aligned"` | 不是遗漏；不是 `U*sin(chi)` | DP-30 |

### 2. 技术规约表（六类）

#### 坐标系

| 规约 | 内容 | 来源 | 关联 DP | 与现状差异 |
|---|---|---|---|---|
| 全局 | WGS84/UTM zone 33N（EPSG:25833，More og Romsdal）| [R17][R54] DESIGN_DECISION | DP-05,18 | 当前一致 |
| 当地 | ENU（East-North-Up，平面 xy）| [R3][R52] DESIGN_DECISION | DP-09,21 | 当前 `do_list` state `[x,y,Vx,Vy]` 是 ENU 一致 |
| 船体 | body-frame x-forward/y-port | [R22][R43] DESIGN_DECISION | DP-10,30 | PSB `[x,y,chi,U]` 是全局非 body；映射时旋转 |
| 原点 | scenario-defined（head_on 窗口 `[39400,6957400]`）| [R17] DESIGN_DECISION | DP-05 | 当前一致 |
| 转换链 | WGS84 → UTM（pyproj always_xy）→ ENU 平面 → body（绕 chi 旋转）| [R52] Shapely 平面要求 | DP-21 | 须显式投影链 |

#### 物理量单位

| 物理量 | 单位 | 来源 | 关联 DP |
|---|---|---|---|
| 位置 x,y | m（ENU）| [R3] SI | DP-09 |
| 航向 psi/chi | rad（内部）/ deg（显示）| [R43] DESIGN_DECISION | DP-10,22 |
| 速度 u,v,U | m/s | [R3] SI | DP-10 |
| 角速度 r,psi_dot | rad/s | [R44] SI | DP-10 |
| 加速度 | m/s² | SI | DP-10 |
| 力 Fx,Fy | N | [R44] SI | DP-30 |
| 距离/clearance | m | [R52] SI | DP-21 |
| 时间 t,sim_time | s | [R29] SI | DP-12 |
| elapsed_ms,t_solve | ms（性能诊断）| [R9] DESIGN_DECISION | DP-14 |
| 船长/宽/吃水 | m | [R22] SI | DP-15 |

#### 符号约定

| 符号 | 正向 | 零点 | 来源 |
|---|---|---|---|
| chi/psi（航向）| 顺时针 from North（海事约定）| 0=正北 | [R43] |
| r/ROT | 右转正 | — | [R22] |
| relative_bearing β | target 相对 ownship，signed | ownship 艏向 | [R62] |
| contact_angle α | ownship 相对 target = β+180° | target 艏向 | [R62] |
| signed_tcpa | 负=CPA 已通过 | — | [R59] |
| port/starboard | starboard=右舷=β∈(0,180) | — | [R61] |

#### 时序约定

| 规约 | 内容 | 来源 | 关联 DP |
|---|---|---|---|
| 时间戳基准 | ROS2 steady / sim clock（Session 唯一）| [R29] DESIGN_DECISION | DP-16 |
| 仿真步 dt_sim | 0.5s（canonical）；V1 须为所有周期整数倍 | [R22] DESIGN_DECISION | DP-16 |
| solve 周期 | 算法声明（SB-MPC 5s / Custom MPC 声明）；RunSpec 可覆盖 | [R3] DESIGN_DECISION | DP-12 |
| 首次 solve | t=0（solve_id=1）| [R29] DESIGN_DECISION | DP-12 |
| horizon col-0 | solve-time 当前状态（t_solve）| [R3] DESIGN_DECISION | DP-10 |
| hold 步 | 保留 horizon 原点 t_solve，按 t_now 采样 | [R29] DESIGN_DECISION | DP-12 |
| phase | 同一 t 完成 env→sensor→tracker→plan→control，再积分 | [R29] DESIGN_DECISION | DP-16 |

#### 数值边界

| 物理量 | 可行域 | 饱和/无效 | 来源 |
|---|---|---|---|
| u（Viknes）| [0, 10] m/s | 钳位 | [R22] |
| ROT（Viknes）| [-15, 15] deg/s | 钳位 | [R22] |
| 正向力 | [0, 13100] N | 钳位 | [R22] |
| grid_size | (0, beam)（beam=2.71m，故 <<2.71）| ≥beam 拓扑坍缩 | [R53] |
| horizon N | ≥1（G3 须完整非空）| N=1 仅 G2 | [R3] |
| TCPA | signed（可为负）| 负=post-CPA | [R59] |
| cov eigenvalues | ≥ -ε（PSD）| <-ε = INVALID_INPUT | DESIGN_DECISION |
| 无效值表示 | NaN=故障/未扫描；-1=无效 | — | [R30] |

#### 接口语义

| 字段 | 含义 | 缺失/无效处理 | 来源 | 关联 DP |
|---|---|---|---|---|
| `9xN` plan | 控制器兼容参考 | shape≠(9,N)→NUMERICAL_FAILURE | [R3] | DP-10 |
| selected_command | 首列执行指令 | 缺失→保持上一值 | [R3] | DP-10 |
| solve_id | 真实 solve 单调递增 | hold 步不增 | [R9] | DP-12 |
| Track age | 距 last_detection_time | 超阈值→degraded（不拒绝）| [R30] | DP-09 |
| covariance | NED/ENU 4x4 PSD | 非 PSD→INVALID_INPUT | [R3] | DP-09 |
| length/width | 目标船尺度 | 缺失→INVALID_INPUT | [R3] | DP-09 |
| PlanStatus | 六态 | 见 DP-13 | [R9] | DP-13 |
| capability_profile_id | {rule}:{scenario}:{algorithm}:{tracker} | — | [R8] | DP-24 |

### 3. 方案包组装（八组件，顺序固定）

方案包独立成文：`docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md`。八组件：

1. 术语表（见上 §1）
2. 技术规约表（见上 §2）
3. 决策卡片集（Step5 最终裁决，见 Step5 章节）
4. 证据矩阵（Step3 完整溯源，见 0.4 节 [R1..R79]）
5. 技术分解完整树（TD-01..04 及子模块裁决，见 0.2 节 + Step4）
6. 弃用方案及理由（见 0.7 节 ALT-01..18）
7. 需求场景 + 验收边界（见 0.5 节 SC-01..10 + 各 DP 失效边界）
8. 已知冲突与未闭环盲区（见下）

#### 8. 已知冲突与未闭环盲区

**已知冲突（经 DESIGN-IT-TWICE 解决）**：
- DP-30 PSB `v`：采纳 `v:=0, method="native_assumption_course_aligned"`（VR-30）。若未来 body-frame 评价要求非零 sway，标 profile 冲突回炉 design-grounding。

**EXTERNAL_CONFIRMATION_REQUIRED（诚实边界，不阻塞 V1）**：
- BL-02：Agder_utm33.gdb + 历史许可
- BL-04：FCB45 速度/水深/操纵包线
- BL-40/48/49：FCB45 实船转移误差/robustness range
- BL-55：目标海域 metocean range
- BL-69：CATZOC 数值精度表（S-52/Ch.2）

**UNKNOWN（实现期裁决，不阻塞设计）**：
- BL-65/66：具体容差数值（grid_size/细分阈值）
- BL-72：最大角点位移上界实现细节
- BL-75：route_exit/terminal_state 具体阈值
- BL-80：canonical set 具体 t-way/seed 数
- BL-83：HCI 证据
- BL-84：maritime 特定 auto-promotion 标准
- BL-113：PSB INFEASIBLE 区分

### 4. 方案包契约（brainstorming 权限边界）

- ✓ 可做：工程细节设计（架构/组件/数据流/错误处理/测试），已裁决方案内优化拔高。
- ✗ 不可做：推翻已裁决核心方案（VR-01..31），除非发现**新矛盾证据**（回炉 design-grounding）。
- ✗ 不可做：重提已弃用方案（ALT-01..18）。
- ✗ 不可做：擅自修改技术规约（单位/坐标系/符号），需改则回 design-grounding 重新裁决。

### 5. 移交 + Step6 完成

- 方案包独立成文：`docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md`（八组件）。
- 决策树日志标状态 `已交付 brainstorming`。
- Step6 完成门检查（design-grounding SKILL）：
  - ✅ 术语表全（17 术语，定义/含义/边界/DP）。
  - ✅ 技术规约表无遗漏无歧义（六类：坐标系/单位/符号/时序/数值边界/接口语义）。
  - ✅ 方案包八组件齐（术语/规约/决策卡片/证据矩阵/技术分解/弃用/场景/冲突盲区）。
  - ✅ 契约明确（brainstorming 权限边界）。
  - ✅ DECOMPOSITION 闭环（TD-01..04 无 INCOMPLETE）。
- 不自动调用 brainstorming；等待用户明确"接受"方案包。
