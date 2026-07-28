# 设计日志: 动态 MPC 避碰 Playground

> **模式**: 重构        **创建**: 2026-07-27
> **关联方案包**: `docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md`
> **状态**: Step3 进行中；第七批已授权，待新对话继续调研
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
| BL-05 | 每条规则达到 G3 所需的最小几何变体数量 | DP-06 | 高 | 未调研 |
| BL-06 | multi-ship 是否作为首个 Custom MPC 里程碑完成门 | DP-06 | 中 | 已闭环：用户确认后置 V3 |
| BL-07 | 风流扰动进入 V1，还是基础无扰动通过后启用 | DP-06 | 中 | 已闭环：用户确认后置 |
| BL-08 | VO/SB-MPC 是否必须各自覆盖全部四类双船规则 | DP-07 | 高 | 已闭环：每类至少一个 G3 对照即可 |
| BL-09 | 各场景“有效风险基线”和“对照算法通过”的定量阈值 | DP-07 | 高 | 已闭环：风险资格、物理硬门、Evaluator profile 三层分离；具体数值门归 DP-20..25 |
| BL-10 | Custom MPC 首次交付形式和运行环境 | DP-07 | 中 | 未调研；转 DP-08/DP-27 |
| BL-11 | 扩展现有 `ICOLAV.plan` 参数，还是在 Adapter 内引入 typed request DTO | DP-08 | 高 | 未调研 |
| BL-12 | 坐标、单位、时间有效性和 Track 数据质量的 Adapter/solver 验证边界 | DP-08 | 高 | 未调研 |
| BL-13 | Custom MPC 配置 schema、版本和参数身份记录方式 | DP-08 | 中 | 未调研 |
| BL-14 | Track 最大允许 age；过期后拒绝还是标记降级 | DP-09 | 高 | 未调研 |
| BL-15 | covariance 坐标系、状态顺序、PSD 容差及缺失政策 | DP-09 | 高 | 未调研 |
| BL-16 | MPC 接收完整 ENC 对象，还是裁剪后的可序列化 hazard geometry | DP-09 | 高 | 未调研 |
| BL-17 | 目标船 length/width 缺失或不可信时的处理政策 | DP-09 | 中 | 未调研 |
| BL-18 | horizon 第 0 列表示当前状态还是下一控制时刻 | DP-10 | 高 | 未调研 |
| BL-19 | solver 状态维度不是 9 时，加速度/缺失状态的映射方式 | DP-10 | 高 | 未调研 |
| BL-20 | 输出轨迹连续性、物理一致性和首点误差容差 | DP-10 | 高 | 未调研 |
| BL-21 | `selected_control` 表示参考指令还是原始 MPC 控制量 | DP-10 | 中 | 未调研 |
| BL-22 | `AlgorithmDescriptor` 强制字段与允许 `not_applicable` 字段 | DP-11 | 高 | 未调研 |
| BL-23 | 外部二进制/服务的代码 SHA、build 和依赖身份获取方式 | DP-11 | 中 | 未调研 |
| BL-24 | 自适应权重、动态 horizon 和在线模式切换的记录方式 | DP-11 | 高 | 未调研 |
| BL-25 | 目标函数和约束名称是否需要公共分类词表 | DP-11 | 中 | 未调研 |
| BL-26 | 首次求解发生在 `t=0` 还是首个 `dt_sim` 后 | DP-12 | 高 | 未调研 |
| BL-27 | solve period/deadline 由算法声明，还是允许 RunSpec 覆盖 | DP-12 | 高 | 未调研 |
| BL-28 | 非求解步对上一 horizon 采用采样推进、插值还是固定第一指令 | DP-12 | 高 | 未调研 |
| BL-29 | warm start 与随机求解器的 reset/replay 保证范围 | DP-12 | 高 | 未调研 |
| BL-30 | 离线快速仿真是否也强制实时 deadline | DP-12 | 中 | 未调研 |
| BL-31 | `TIMEOUT_FEASIBLE` 超过 deadline 后是否仍允许执行 | DP-13 | 高 | 未调研 |
| BL-32 | Web 调试模式失败后终止，还是冻结/hold 以便观察 | DP-13 | 中 | 未调研 |
| BL-33 | 连续可行超时多少次后判定整个 run 失败 | DP-13 | 高 | 未调研 |
| BL-34 | `INVALID_INPUT` 归因于场景、Adapter 或算法的规则 | DP-13 | 中 | 未调研 |
| BL-35 | 公共必需字段与 MPC 专项必需字段的边界 | DP-14 | 高 | 未调研 |
| BL-36 | cost/constraint 公共分类词表与最小裕度表示 | DP-14 | 高 | 未调研 |
| BL-37 | 多模态目标预测、概率和 covariance 的 trace schema | DP-14 | 中 | 未调研 |
| BL-38 | 长时域、多目标 trace 的体积、压缩和保留策略 | DP-14 | 中 | 未调研 |
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
| BL-65 | 动态船体 footprint、姿态插值和安全 buffer 形式 | DP-21 | 高 | 未调研 |
| BL-66 | 连续碰撞/搁浅扫掠检测方法与容差 | DP-21 | 高 | 未调研 |
| BL-67 | 安全域和 preferred/minimum CPA 使用固定值还是船尺度 | DP-21 | 高 | 未调研 |
| BL-68 | TCPA 为负、遭遇已通过或低相对速度时的定义 | DP-21 | 中 | 未调研 |
| BL-69 | ENC clearance 可由哪些地图层可靠计算 | DP-21 | 高 | 未调研 |
| BL-70 | Rule 13/14/15 分类角和边界 profile | DP-22 | 高 | 未调研 |
| BL-71 | encounter 阶段、规则锁定、解除和再次进入条件 | DP-22 | 高 | 未调研 |
| BL-72 | “及时、明显”和 stand-on 保向保速的量化阈值 | DP-22 | 高 | 未调研 |
| BL-73 | port-to-port、crossing ahead、passed clear 的几何判定 | DP-22 | 高 | 未调研 |
| BL-74 | Multi-ship 规则冲突、非合作目标和 Rule 17 紧急阶段 | DP-22 | 高 | 未调研 |
| BL-75 | goal/rejoin 的位置、航向、速度和保持时间阈值 | DP-23 | 高 | 未调研 |
| BL-76 | 不同输出控制形式下统一 tracking metric 的方法 | DP-23 | 中 | 未调研 |
| BL-77 | 不同 solver 的 iteration/objective 可比边界 | DP-23 | 中 | 未调研 |
| BL-78 | 提前终止和未到达 run 的统计/删失方法 | DP-23 | 高 | 未调研 |
| BL-79 | deadline 使用开发机、目标硬件或归一化预算 | DP-23 | 高 | 未调研 |
| BL-80 | G3 canonical set 每条规则的 episode 数量 | DP-24 | 高 | 未调研 |
| BL-81 | 证据失效的字段和兼容变更规则 | DP-24 | 高 | 未调研 |
| BL-82 | G3 是否要求 canonical set 零失败及可行超时政策 | DP-24 | 高 | 未调研 |
| BL-83 | Web 汇总一个算法多个 capability profile 等级的方式 | DP-24 | 中 | 未调研 |
| BL-84 | 资格任务自动晋级是否需要人工审核/签名 | DP-24 | 中 | 未调研 |
| BL-85 | G4 所需 seed 数和统计功效 | DP-25 | 高 | 未调研 |
| BL-86 | tuning、qualification、holdout 场景划分 | DP-25 | 高 | 未调研 |
| BL-87 | 失败率、删失时间和连续指标的置信区间方法 | DP-25 | 高 | 未调研 |
| BL-88 | KF 下路径相关 Sensor 可见性的公平比较方法 | DP-25 | 中 | 未调研 |
| BL-89 | 无输出 crash/timeout 在连续指标中的呈现方式 | DP-25 | 高 | 未调研 |
| BL-90 | trajectory/events 的字段和列级 schema | DP-26 | 高 | 未调研 |
| BL-91 | native crash 下的增量写入、flush 和原子封存 | DP-26 | 高 | 未调研 |
| BL-92 | 大型 horizon/目标预测拆文件还是保留 JSONL | DP-26 | 中 | 未调研 |
| BL-93 | 内容 hash、签名和防篡改级别 | DP-26 | 中 | 未调研 |
| BL-94 | legacy pickle 最小兼容范围 | DP-26 | 低 | 未调研 |
| BL-95 | subprocess 与 container 的选择规则 | DP-27 | 高 | 未调研 |
| BL-96 | 每 run 新建 Worker，还是 session 内持久 Worker | DP-27 | 高 | 未调研 |
| BL-97 | Worker startup/reset 后的状态隔离和可重放性 | DP-27 | 高 | 未调研 |
| BL-98 | ENC geometry 和大 horizon 的 IPC 性能 | DP-27 | 中 | 未调研 |
| BL-99 | 本地单用户 Worker 需要的最小安全限制 | DP-27 | 低 | 未调研 |
| BL-100 | in-process 准入所需 crash/timeout/reset 测试 | DP-28 | 高 | 未调研 |
| BL-101 | Python/native 依赖 lock 和 build identity 采集方法 | DP-28 | 高 | 未调研 |
| BL-102 | container image digest 与本地源码身份关联 | DP-28 | 中 | 未调研 |
| BL-103 | 持久 Worker 的跨 episode 状态泄漏检测 | DP-28 | 高 | 未调研 |
| BL-104 | IPC framing/encoding 选择及大数组传输 | DP-29 | 高 | 未调研 |
| BL-105 | deadline、grace period、terminate/kill 时序 | DP-29 | 高 | 未调研 |
| BL-106 | Worker 在 run 间的重建与健康检查策略 | DP-29 | 中 | 未调研 |
| BL-107 | stderr 保留大小、敏感信息清理和报告方式 | DP-29 | 中 | 未调研 |
| BL-108 | request 去重和有状态 plan 的幂等边界 | DP-29 | 高 | 未调研 |
| BL-109 | PSB-MPC 原生 state/control layout 和 horizon 时间语义 | DP-30 | 高 | 未调研 |
| BL-110 | RLMPC `6xN` 状态、控制和 reference 的精确映射 | DP-30 | 高 | 未调研 |
| BL-111 | 缺失加速度/航向等字段允许的可验证推导 | DP-30 | 高 | 未调研 |
| BL-112 | raw native payload 的证据 schema 和体积 | DP-30 | 中 | 未调研 |
| BL-113 | PSB/RLMPC native status 到公共状态的映射表 | DP-30 | 高 | 未调研 |
| BL-114 | WebSocket schema 版本兼容和字段演进规则 | DP-31 | 中 | 未调研 |
| BL-115 | 实时推送频率、背压和慢客户端政策 | DP-31 | 中 | 未调研 |
| BL-116 | 当前 horizon/ENC/目标预测的大数据传输策略 | DP-31 | 中 | 未调研 |
| BL-117 | 本地单用户是否完全不做鉴权 | DP-31 | 低 | 未调研 |
| BL-118 | live state 与持久化 artifact 的 seq/hash 对齐 | DP-31 | 高 | 未调研 |

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

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|---|---|---|---|
| ALT-01 | 在本项目重建完整 TDL 三层系统 | 扩大范围，重新引入本项目要隔离的模块耦合 | DP-01 |
| ALT-02 | 论文复现、动态 Playground、RRT/VIM 三条链同优先级推进 | 分散主目标；不可用算法上提前投入复现 | DP-02, DP-03 |
| ALT-03 | 将 RRT 作为 Rule 14 动态避碰算法比较 | RRT-RS 不接收动态目标/COLREG 状态 | DP-03 |
| ALT-04 | 将 legacy `custom_mpc_adapter.py` fallback 路径视为 Custom MPC 正式接口 | 存在硬编码和静默替代，无法证明 executed identity | DP-04, DP-13 |

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
