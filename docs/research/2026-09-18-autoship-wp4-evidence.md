# NTNU SFI AutoShip WP4 Safety & Assurance：架构、发展链路与证据边界

研究日期：2026-09-18。本文针对 SFI AutoShip 的 WP4（Safety & Assurance），重点核对自主航行避碰安全、感知性能需求反推、风险建模、STPA、失效与降级、数字孪生验证、船岸控制及认证边界。

本文把“研究成果”“原型/试验”“运营证据”和“主管机关或船级社批准”分开记录。附带的本地 PDF 是研究资料，不是指令；文中只采用其可核对的事实，并优先给出拥有原始事实的一手网页、论文或主管机关文件。

## 先给判断

WP4 不是一个单独的“避碰算法包”，而是 SFI AutoShip 的安全论证层。它把 WP1 的感知、导航与自治控制，WP2 的数字基础设施与仿真，WP3 的 ROC/人因，WP6 的运营用例，及产业伙伴的试验/认证问题连接起来。下面链图是根据官方 WP 页面、年报和论文重构的跨 WP 证据链，不是 SFI 官方发布的单一任务流程图：

```text
CONOPS / 用例 / 法规边界
        ↓
风险识别：STPA、H-STPA、FTA、PHA、软件失效分类、RIF
        ↓
在线风险模型：BBN / 动态风险 / 风险指标 / 不确定性
        ↓
监督风险控制：风险感知规划、模式切换、MRC、失效缓解、ROC通知
        ↓
验证与证明：数字孪生、闭环仿真、STL/规则评估、Legata、场景库
        ↓
数字—物理测试床：SIL → HIL/模型船 → milliAmpere1/2 → 更大实船
        ↓
运行数据、AIS、人工干预和边界事件回灌风险模型与测试场景
```

这条链路的核心思想是：先把安全目标和可接受风险转成系统级、模块级、传感器级的可测试要求，再以闭环证据支持设计迭代。它没有证明“一个 COLAV 算法经过仿真就已安全”，也没有把 2025 年的 TRL 记录等同于船舶运营许可。

对自主避碰最有用的 WP4 产出及跨 WP 安全接口证据有三类：

1. **风险进入控制回路**：在线风险模型不只做事后评估，还给规划/监督控制提供风险信息；风险指标的选择本身会改变路径和安全性。
2. **从 CA 鲁棒性反推 SA 要求**：把雷达、AIS/GNSS、跟踪器或融合输出施加噪声、偏差、丢失和失效，在闭环中测 CPA、COLREG 行为、航向/速度抖动，再反推感知系统最低性能。
3. **把研究结果变成可审计证据**：场景、规则解释、STL/Legata 约束、仿真配置、模型版本、轨迹、告警和人工干预都要可追溯，之后才能与 NMA、DNV 或其他主管机关讨论等效安全。

归属边界：[官方 WP2 页面](https://www.ntnu.edu/sfi-autoship/digital-infrastructure)把 2025 年两篇“CA 鲁棒性 → SA 性能要求”论文列在 Digital infrastructure；本文把它们作为 WP2 方法对 WP4 assurance 的关键接口使用，不把它们改写成 WP4 自有产出。

## 1. SFI AutoShip 的总体架构与发展定位

### 1.1 中心目标、时间范围和伙伴结构

NTNU 官方主页把 SFI AutoShip 定义为一个 **8 年研究型创新中心**，2020 年 12 月启动，目标是支持挪威产业发展安全、可持续的自主船舶。公开重点包括：态势感知、AI、自主控制、数字基础设施；岸基控制中心和新运营/物流模式；风险监测方法，以及船上没有船长时的法律责任问题。中心拥有 20 多个挪威海事产业伙伴，覆盖终端用户、产品/服务供应商、研究机构、大学和政府部门。

来源：[NTNU SFI AutoShip 总览](https://www.ntnu.edu/sfi-autoship)。2025 年报把中心生命周期写为 **2020–2028**，并记载 2025 年已过中期评估，研究开始由概念转向更成熟的结果、实现和影响。

2025 年报的组织页显示：中心由 NTNU 工程控制系（ITK）承载，NTNU 总计有三个学院、六个系参与；研究伙伴包括 SINTEF Ocean、SINTEF Digital、IFE 和 UiO。中心治理包括 Centre Board、Centre Management、8 个 Work Packages 和两个 advisory committees；产业伙伴 DNV、Equinor、Fugro、Kongsberg Maritime、Maritime Robotics、Massterly、Torghatten、NMA 等进入治理或用例协作结构。

来源：[SFI AutoShip Annual Report 2025，组织与研究章节（官方 PDF）](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2025.pdf/9dc32b39-98e6-93ff-fd55-695a9da0dbd0?t=1774619719616)，印刷 pp. 4–17。当前研究网页主要列出 7 个研究/创新 WP；年报同时保留第 8 个管理、传播与 dissemination WP。两种页面呈现应理解为“7 个业务 WP + 1 个中心管理 WP”，而不是中心只有 7 个工作包。

### 1.2 8 个 WP 的安全接口

年报给出的中心研究问题是：社会如何从自主航运获得环境、经济、安全和可持续收益；新标准、方法、法规、数字孪生和数字基础设施如何保证自主航运的安全与安保。研究以 use case 对齐，而不是只按单一算法课题组织。

与 WP4 的直接接口可以概括为：

| WP | 对 WP4 的输入/输出关系 |
|---|---|
| WP1 AutoRemote | 感知、跟踪、导航、控制、靠泊和避碰候选系统；WP4 将其安全目标、运行边界和失效模式转成要求和验证证据。 |
| WP2 Digital infrastructure | 仿真、数据、通信、数字孪生和场景基础设施；WP4 用它们做风险模型训练/更新、闭环验证和大规模测试。 |
| WP3 ROC & human factors | 远程监控、接管、HMI、责任与人的可靠性；WP4 的 H-STPA、MRC 和风险告警需要这些人因输入。 |
| WP4 Safety & assurance | 风险识别、在线风险、失效安全、验证/仿真、COLREG 与责任/法规。 |
| WP5 Sustainable operations | 航线、能源、货物/作业约束等运行条件；这些是风险影响因素和 operational envelope 的一部分。 |
| WP6 Use cases | 深海货运、短海运输、城市客运、海上支持等具体 CONOPS、数据和边界事件；风险模型必须绑定用例，不能脱离场景宣称泛化。 |
| WP7 Innovation & commercialisation | 把研究成果按 TRL 与创新成熟度整理，推动产业利用和第三方讨论。 |
| WP8 Management/communication/dissemination | 中心管理、传播和研究成果汇总。 |

WP2 的官方边界是其自身的 digital infrastructure 研究、数据/通信/仿真组件及相关数字孪生工作；它不是“全中心统一数字孪生底座”的官方表述。WP4 只使用与自身风险建模、场景验证和 assurance 相关的接口与资产。

中心并非只把论文留在实验室：官方新闻记录了年度跨 WP workshop、产业伙伴共创、NMA/ DNV/运营商参与的风险工作坊、研究者创新训练，以及 2024 年 SFI Director 在 IMO MSC 109 介绍中心结构和自治方向。来源：[NTNU News & Events](https://www.ntnu.edu/sfi-autoship/news/)，尤其 workshop、IMO 和 use-case site visit 条目。

## 2. WP4 官方边界、任务和研究组合

### 2.1 四个官方任务

官方 WP4 页面给出的目标是“为自主船舶的风险管理、安全设计和安全运行研究、开发新方法、模型和工具”。安全对象包括技术、软件、网络安全、人和组织措施；范围覆盖设计、系统、运行及关联基础设施。

四个主任务为：

- **Task 4.1：运行中的风险管理**。监测系统状态，对危险事件采取行动，并减轻后果。
- **Task 4.2：设计阶段的安全集成与 fail-safe**。把安全前置到设计阶段，处理故障、冗余、降级和安全状态。
- **Task 4.3：系统验证与仿真**。发展包括低成本测试和仿真在内的验证方法。
- **Task 4.4：自治运行的法律、责任和风险接受**。研究 liability、maritime law、标准、规则和 assurance 工具如何覆盖自治运行的新问题。

来源：[NTNU WP4 Safety & Assurance](https://www.ntnu.edu/sfi-autoship/safety)。该页面同时列出 WP Leader Ingrid Bouwer Utne，以及 Gezer、Kristensen、Krågebakk、Lee、Lundteigen、Skjetne、Solvang、Sreedharan、Tailoussane、Wallner 等研究人员；项目列表包含在线风险、漂流搁浅、数字孪生安全证明、COLREG 法律、海事控制安全、COLREG 评估、AI 数据驱动安全管理等。

### 2.2 WP4 项目如何拼成一套 assurance architecture

| 研究支柱 | 官方问题 | 2025 证据/技术路线 | 适用的安全问题 |
|---|---|---|---|
| 在线风险建模 | 自治系统如何自行评估运行风险并支持决策 | STPA/风险影响因素 → Bayesian/online risk model → 规划与控制；Grethe ASV 仿真和 field trials | 碰撞、搁浅、环境/系统状态变化、风险指标选择 |
| 漂流搁浅与失去指挥 | 推进、电力生成/分配或转向失效如何造成 loss of command | AIS 暴露量修正的事故率和风险影响因素；机械系统设计、维修和 power management | 失去动力、通信/电力冗余、漂移路径、港口/沿岸应急 |
| 安全控制与模式切换 | 正常模式、故障模式、MRC 如何安全切换 | symbolic control、STL、NMPC、CBF、BBN、模块化数字—物理 testbed | 降级、保守停车、保持位置、接管前的安全窗口 |
| 感知—避碰闭环 | 感知误差怎样改变 CA 安全与 COLREG 行为 | 传感器噪声/失效注入、DCPA、course/speed change、STL robustness | 反推雷达/跟踪/融合要求，防止独立模块指标脱离闭环 |
| 规则与法律机器化 | 人类规则如何变成可计算、可审计要求 | Legata DSL、runtime resolvers、rule automata、HPC simulation capsules | 规则解释、地域规则变化、量化合规证据、法律不确定性 |
| 数字孪生安全证明 | 如何用大量场景证明复杂自治系统 | 数字孪生映射真实控制单元，场景化安全验证和 operational planning | 代表性场景、边界工况、仿真可信度、第三方审查 |
| AI/海况安全管理 | 数据驱动 agent 如何显式感知风险 | 风险感知 DRL、collision probability、可解释输出；波面/流场估计 | 噪声下的鲁棒性、模型不确定性、运行时监测 |

## 3. WP4 innovation leads 与成熟度：研究是什么，离认证有多远

官方 Innovation 页面说明，每个 innovation lead 都按“problem statement、proposed solution、purpose/value”整理，并用 TRL 1–9 和简化的 KTH Innovation Readiness 维度跟踪成熟度。这是产业转化管理工具，不是船级社证书。

来源：[SFI Innovation leads 总览](https://www.ntnu.edu/sfi-autoship/innovationleads)；[WP4 innovation leads](https://www.ntnu.edu/sfi-autoship/wp-4-innovation-leads)。官方 WP4 页面给出的逐项内容如下：

| Lead | 官方描述 | 2025 年报的成熟度/证据边界 |
|---|---|---|
| Marine cybernetics and safety | 解决正常运行模式与 safety fallback 模式间安全、无缝切换；模块化 testbed 降低自治测试成本和风险 | 年报将模块化 autonomy safety testbed 列为 TRL 3；有数字—物理试验，但不是实船运营许可。 |
| AI and data-driven safety management | 用极化立体相机、GNSS/IMU 和 ML 估计三维波面、速度/压力场；Ægir-Frames 以 REEF3D 数据生成训练输入 | 解决环境状态估计和轨迹预测问题；不应把模拟海况数据或估计模型直接视为经实船认证的传感器。 |
| COLREG evaluation system | Legata DSL 表达海事规则，runtime resolver/rule automata 大规模仿真，输出定量合规分数，支持 HPC 容器和数字孪生/传感器测试 | 代表可审计的规则解释和测试工具；分数依赖规则编码、参数和场景，不等于主管机关作出的法律结论。 |
| Risk-aware AI agents | 以安全文献定义 risk awareness，训练 DRL agent 估计碰撞概率，并把可解释风险估计接入策略 | 2025 为 WP4 官方 innovation lead 的研究/仿真原型，与 DNV 合作讨论风险感知和验证；不能把“可解释碰撞概率”当成已获批的安全功能。 |
| Online risk modeling | 碰撞和搁浅风险模型接入 supervisory risk control；模型利用不同数据更新风险，并以仿真和真实试验验证 | 年报明确将 collision/grounding online risk modelling 列为 **TRL 5、已有 trial demonstrations**；仍需用船、传感器、运行域和批准条件进行独立验证。 |
| Methods/tools for drift grounding | 研究 loss of command 的频率、后果和风险影响因素，指导机械设计、维修、电力管理和导航决策 | 年报将 drift grounding mitigation 列为 TRL 3；Dugan 于 2026-02-18 通过首个 WP4 PhD 答辩，成果不能替代船级社 machinery approval。 |
| Safety demonstration using digital twin | 用数字孪生和场景仿真覆盖正常到关键边界情况，支持设计验证、认证讨论和运行规划 | 年报将 digital-twin safety validation 列为 TRL 2；属于方法和证明框架早期阶段，不是数字孪生本身获得认可。 |

来源：[Annual Report 2025，年报 portfolio 摘要](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2025.pdf/9dc32b39-98e6-93ff-fd55-695a9da0dbd0?t=1774619719616)，印刷 pp. 51–52；[WP4 innovation leads](https://www.ntnu.edu/sfi-autoship/wp-4-innovation-leads)。年报还记录 2025 年中心总计 23 篇 journal articles、17 篇 conference papers，说明学术产出活跃，但论文数量不等于集成系统成熟度。

本地下载的 [Towards Safety Aware AI Agents.pdf](</Users/marine/Documents/Paper/Towards%20Safety%20Aware%20AI%20Agents.pdf>) 是德国 Bundeswehr University Munich Institute for Autonomous Systems Technology 的 project MORE 外部论文，资助信息为 dtec.bw；它不是 SFI AutoShip/WP4 论文。其“碰撞概率分布 + safety-aware RL”与 WP4 的 Risk-aware AI lead 在方法上相关，但不能作为 WP4 归属或 NTNU 试验依据。WP4 的独立归属以[官方 innovation lead 页面](https://www.ntnu.edu/sfi-autoship/wp-4-innovation-leads)中 Paul Lee/ Ingrid B. Utne 条目为准。

## 4. 关键研究链路与原始论文证据

### 4.1 STPA → BBN/在线风险 → 监督风险控制

**方法源头。** Utne 等人的 supervisory risk control 研究把风险管理能力放进自主船控制系统，而不是只做离线 HAZID。该路线随后发展为：

```text
CONOPS / 控制结构
 → STPA / H-STPA / FTA / PHA
 → 危险事件、UCA、风险影响因素和监测变量
 → BBN/动态概率风险模型
 → risk cost / risk metric / 可接受路径
 → SRC 选择路线、模式、速度、机械状态或 MRC
 → 场景验证与运行数据更新
```

核心来源：

- [Utne et al., “Towards supervisory risk control of autonomous ships”, RESS 2020, DOI 10.1016/j.ress.2019.106757](https://doi.org/10.1016/j.ress.2019.106757)。论文将 supervisory risk control 定义为能在运行中评估并控制风险的动态功能。
- [Yang & Utne, “Towards an online risk model for autonomous marine systems”, Ocean Engineering 2022, DOI 10.1016/j.oceaneng.2022.111100](https://doi.org/10.1016/j.oceaneng.2022.111100)。论文用系统工程要求比较 PHA、STPA 和 procedural HAZOP，强调在线模型要接收多源/传感器数据、及时反映运行变化、更新模型和场景、处理 RIF 相关性及传感器/融合不确定性。
- [Johansen & Utne, “Human-autonomy collaboration in supervisory risk control of autonomous ships”, JMET 2024, DOI 10.1080/20464177.2024.2319369](https://doi.org/10.1080/20464177.2024.2319369)。论文使用 STPA + Human-STPA + BBN + SRC；SRC 在达到运行边界前通知 ROC 操作员，风险过高时进入 MRC。该案例明确将远程监督员、通知时间、信息量和接管作为安全控制结构的一部分。
- [Yang et al., “Online risk modeling of autonomous marine systems: Case study of autonomous operations under sea ice”, Ocean Engineering 2023, DOI 10.1016/j.oceaneng.2023.114765](https://doi.org/10.1016/j.oceaneng.2023.114765)。论文将 STPA 和 BBN 结合，使用模糊离散化处理证据不确定性，并提出基于在线风险等级的两级 supervisory risk control；案例是冰下 AUV，不能直接当成 MASS 认证证据，但说明 WP4 方法如何从 hazard analysis 进入运行控制。

**STPA 与安全/网络安全边界。** [Kristensen, Dallolio & Utne, “A systems approach to hazard identification for solar-powered and wave-propelled unmanned surface vehicle”, JMET 2024, DOI 10.1080/20464177.2024.2315646](https://doi.org/10.1080/20464177.2024.2315646) 把 STPA、STPA-Sec/STRIDE 与绿色能源交互扩展到同一 hazard identification：通信丢失、信息不足、能量管理和自治功能相互作用会形成不安全控制动作。该文还用 AutoNaut 运营经验核对结果，并讨论由 hazard identification 继续构建 online risk model 的路线。

### 4.2 风险指标不是中性参数

[Kristensen et al., “Evaluating the effect of risk metrics for supporting operational decision-making by autonomous surface vehicles”, Ocean Engineering 2025, DOI 10.1016/j.oceaneng.2025.121937](https://doi.org/10.1016/j.oceaneng.2025.121937) 是 WP4 2025 年最直接的控制接口证据之一。研究比较 expected economic loss、individual risk、hazardous-event probability 三种风险指标，把它们用于 ASV 跟随 AUV 的路径规划，并同时做仿真和 Trondheim fjord 的真实 ASV field trials。结论是风险指标会改变计划路径；风险模型接入控制或 supervisory risk controller 时，指标选择必须按其对安全和决策的影响来设计。

这意味着工程上不能只规定“风险输出一个数”。应明确：风险数值对应什么事故、时间窗、后果、暴露量和接受准则；规划器怎样使用它；在效率、COLREG、碰撞、搁浅和失去控制之间如何排序。风险模型的“可解释”和“可审计”比单次仿真中的最低代价更重要。

### 4.3 漂流搁浅、loss of command 与系统级可靠性

[Dugan & Utne, “Improved identification of maritime risk-influencing factors using AIS data in regression analysis”, RESS 2025, DOI 10.1016/j.ress.2025.111156](https://doi.org/10.1016/j.ress.2025.111156) 针对 2017–2021 年挪威水域货船 loss of command（推进、电力或方向控制丢失），用 AIS 派生活动量作为 exposure/offset 估计事故率，改善 RIF 识别。显著因素包括船旗、船舶管理人所在地、检查缺陷、推进冗余和单一燃料配置；研究可支持高风险船识别和 VTS 决策。

这项结果对应 WP4 的真实工程边界：避碰安全不只等于“目标船距离够不够”，还包括自身推进、电源、转向、通信和维修状态。对于无人船，动力/电力故障可能把一个本来可控的避碰场景转成 drift grounding 或无法执行的 MRC。

[Gomola, Kristensen & Utne, “Multi-level risk classification of distributed embedded software failures for autonomous systems”, Journal of Risk and Reliability 2025, DOI 10.1177/1748006X241309170](https://doi.org/10.1177/1748006X241309170) 将软件失效的原因、后果、过程关系和系统抽象层级整理成可迭代 taxonomy，并用 MASS 的 navigation/collision-avoidance subsystem 做 case study。论文特别区分 software reliability 与 software safety，并强调从概念设计、详细设计、验证到确认都要反复更新失效分类。

边界：该 taxonomy 是 hazard/failure identification 与要求生成工具，不是 software failure probability 的通用数据库，也不自动证明某个分布式 ROS/控制系统安全。

### 4.4 跨 WP2–WP4：从 CA 鲁棒性反推 SA/传感器性能要求

这是 WP2 支撑、可直接用于 WP4 assurance、也最适合用户自主避碰研发的路线：**不要先单独给雷达/跟踪器定一个看似漂亮的精度阈值，再假设 CA 能适应；应由系统级安全结果反推允许的 SA 误差包络。**

#### Closed-loop simulator（ESREL 2025）

[Løvoll et al., “Leveraging Collision Avoidance Robustness to Establish Situational Awareness Requirements: A Closed Loop Simulator Approach”, ESREL 2025, DOI 10.3850/978-981-94-3281-3_ESREL-SRA-E2025-P3941-cd](https://doi.org/10.3850/978-981-94-3281-3_ESREL-SRA-E2025-P3941-cd) 使用模块化低保真闭环：scenario → simulator → SA → CA → action control → ship state。SA 从 ground truth 生成目标船位置/速度/艏向，注入可控 Gaussian noise 和 bias；CA 用 SB-MPC 简化版本，action control 含 ALOS 和 PID；输出用 DCPA 和大于 10° 的显著航向变化评价安全/避碰行为。

论文在每个噪声水平做 1000 次仿真。代表性结果：crossing 场景 DCPA 从无噪声约 358 m 降到 σ≥8 m 时约 330 m；head-on 场景从约 374 m 降到 σ>15 m 时约 365 m。course-change 数量也随噪声增加；head-on 在 σ>9 m 后变化明显，crossing 本来就更容易产生多次航向变化。结论是 CA 对 SA 误差具有 encounter-dependent robustness，感知要求必须按场景、CA 更新策略和安全目标定义。

#### 多传感器降级与 STL（ICMASS 2025）

[Morris et al., “From COLREG compliance to performance requirements for situational awareness systems in autonomous navigation systems”, JPCS 2025, DOI 10.1088/1742-6596/3123/1/012010](https://doi.org/10.1088/1742-6596/3123/1/012010) 将系统分为 SA、CA 和 Action Control 三个功能块，配置 GPS/AIS 与 radar 的独立噪声/失效模型，用简单融合生成目标位置，再用 CPA、航向/速度变化和 Signal Temporal Logic robustness 评价规则满足程度。STL robustness 大于 0 表示满足要求，小于 0 表示违反；论文展示了传感器噪声增加后 CPA、估计误差和 Rule 2 失败率/分数方差的变化。

两篇官方归属 WP2 的论文共同给出可审计的需求推导方法；WP4 可把这些方法接入自己的风险目标、场景库和 assurance evidence：

```text
安全目标（不碰撞/不搁浅/不违反指定规则）
 → CA/控制器表现指标（CPA、DCPA、操纵次数、STL robustness、任务完成）
 → SA 误差模型（噪声、偏差、延迟、丢失、误检、漏检、track death）
 → 统计试验/边界搜索
 → 传感器、跟踪、融合和健康监测的性能要求
```

两篇论文也明确限制了结论：低保真模型不含真实风浪流，场景/船型有限；雷达/GPS 传感器很简化，失败模式没有基于真实统计；DCPA 和航向变化只是部分指标；后续仍需 grounding、ENC、非 COLREG 交通、GPS jamming/AIS spoofing、执行器故障、false positive/negative 和更真实的 tracker/fusion。数值结果可作为方法演示，不能直接迁移为当前 MASS 的安全阈值。

### 4.5 COLREG 量化评估与机器可执行规则

[Hagen et al., “Safety and COLREG evaluation for marine collision avoidance algorithms”, Ocean Engineering 2023, DOI 10.1016/j.oceaneng.2023.115991](https://doi.org/10.1016/j.oceaneng.2023.115991)（NTNU 与 Kongsberg Maritime）给出自动评估避碰轨迹的数学规则和安全/COLREG 分数，使用仿真 encounter 和正常运营船轨迹核对方法。其贡献包括 maneuver detection、Rules 8 和 13–17 的指标、参数/权重以及对真实轨迹的 penalty 解释；同时明确指出 COLREG 语言有意保留判断空间，角度、速度、距离等参数不能假装是唯一法律真值。

2025 年报和官方 innovation lead 页面显示，Sreekant Sreedharan 的后续方向把这一类评估扩展为 **Legata DSL + runtime resolvers/rule automata + containerized HPC simulation capsules**，并输出规则合规分数和可审计报告。此路线的 assurance 价值在于让“文字规则 → 机器解释 → 场景 → 轨迹 → 分数”可复查；但规则编码仍是工程/法律解释，需要与 NMA、主管机关、运营边界和其他船舶行为共同审查，分数本身不是法律裁决。

### 4.6 数字孪生、数字—物理测试床与闭环验证

[Gezer et al., “Digital-physical testbed for ship autonomy studies in the Marine Cybernetics Laboratory basin”, arXiv:2505.06787（v5, 2026-07-17；2025 ICSOS 工作基础）](https://arxiv.org/abs/2505.06787) 给出 WP4/Marine Cybernetics 的数字—物理验证链：

```text
低保真模型（接口/高层逻辑）
 → mcsimpy 高保真水动力/环境模型（GNC tuning）
 → Stonefish 传感器/视觉/交互模拟
 → Unity digital twin + remote control center
 → HIL/32 m × 6.4 m wave basin/Cybership fleet
 → semi-full-scale milliAmpere1
 → full-scale R/V Gunnerus
```

论文还强调同一套模块化控制/估计接口在 simulation 和物理模型间复用，支持 remote control、formal verification 和 autonomy experiments；公开了 hydrodynamic dataset、mcsimpy、shoeboxpy 和 C/S software suite 的 Zenodo 资源。

**必须保留的限制。** 44 个波浪/系泊试验中，模拟相对物理测量的回归斜率约为 X=1.63、Y=1.30、N=2.08；论文解释了 WAMIT 船体长度、吃水、质量、封闭 turret 等模型差异。作者明确写出：小尺度 Froude–Reynolds 缩比冲突、高保真模型未解析黏性和强非线性、全舰队 bollard-pull 尚未完成、验证只覆盖部分舰队、水动力数据不确定性没有传播到物理实验，实验室环境也不代表真实海况。故这是一条优秀的验证基础设施路线，但不能写成“从数字孪生到真船已经完成等价证明”。

## 5. milliAmpere1/2：工程验证和运营尝试的真实边界

### 5.1 milliAmpere2 是原型化运营试验，不是无人运营认证

[Eide et al., “The Autonomous Urban Passenger Ferry milliAmpere2: Design and Testing”, JOMAE 2025, DOI 10.1115/1.4067370](https://doi.org/10.1115/1.4067370) 是最完整的 MA2 公开工程报告。它描述 8.65 m、6 t、4 个 10 kW azimuth pods、最多 12 人的城市客运原型；2022 年在 Trondheim 进行了三周 public trial。论文围绕人因、能源/推进、自治系统、ROC 远程控制和风险评估五个问题组织，而不是只报告一次避碰成功。

与 WP4 直接相关的证据：

- 论文把自治系统的目标/架构描述为 **Degree 4**，并把需要人工介入时回退到 **Degree 3** 作为设计模式；2022 public trial 期间安全员仍在船上，论文将把安全员迁移到 ROC、实现更强远程运行写作后续路径。不能把 Degree 4→3 写成 2022 试航已经完成的远程接管运行。
- 风险分析使用两轮 PHA 和专家判断；关键 hazard 包括近距离小艇/皮划艇、失电失控、网络攻击、乘客跌倒和恶劣风流。措施包括冗余电池管理、fail-to-safe、紧急锚、网络安全设计、生命救生设备和超出海况限制时停止运营。
- 三周试航约有 **25 次人工干预**。一个边界事件是系统把自身尾流当作目标，触发不必要的加速/避让；另一个是暴风雨后的漂浮树叶被跟踪而停车。工程师在观察后约 24 小时内诊断并更新软件。这是“运行数据 → 边界事件 → 快速修复”的真实闭环，也说明 false track 对 COLAV 安全的影响不能只在理想仿真中讨论。
- 试航期间船上始终有 safety operator，论文明确写出这是 NMA 指南及当前技术/法规约束的要求。乘客对无安全员的安全感调查是“想象条件”，不能等同于已经完成无安全员运行。

因此应分别称为：MA1/MA2 **工程验证与受控试航证据**、研究原型的运营尝试；不能称为“无人客运已经认证”或“已证明可在开放水域自主运行”。

### 5.2 NMA、DNV、IMO：认证/批准层是另一条证据链

**挪威主管机关。** NMA 的 RSV 12-2020 说明，自治/远程操作船要达到与常规船相同的安全水平，依据船型既有法规，并通过 IMO MSC.1/Circ.1455 的 alternatives/equivalents 处理新技术。文件要求根据 autonomy/remote operation 评估；要求 CONOPS、pre-HAZID、safety/design/operation and maintenance philosophy、risk assessment 和 gap analysis 等；定义 third-party verification、MRC、fail-to-safe、HIL 和 simulations；NMA 可给出临时/最终批准和国内航行证书。

来源：[Norwegian Maritime Authority, RSV 12-2020](https://www.sdir.no/en/regelverk/circulars/guidance-in-connection-with-the-construction-or-installation-of-automated-functionality-aimed-at-performing-unmanned-or-partially-unmanned-operations/)。这份文件是“研究结果如何进入主管机关审查”的直接边界，不是 SFI AutoShip 自身的认证声明。

**DNV。** DNV 的公开自动化页面把 `DNV-CG-0264 Autonomous and remotely operated ships`、`DNV-RP-0510 Framework for assurance of data-driven algorithms and models`、第三方 autonomy/remote-control verification、hazard identification 和 Open Simulation Platform 列为规则/服务入口。DNV 的 Simulation Trust Center 案例说明：真实测试覆盖不足，需要云端虚拟硬件、参数化场景、多实例仿真和 vendor simulator validation 来支持 class/certification 讨论。

来源：[DNV Manning & Automation](https://www.dnv.com/maritime/dutch-naval-design/manning-automation/)、[DNV Simulation Trust Center 案例](https://www.dnv.com/research/review-2023/featured-projects/proving-the-case-for-simulation-based-testing/)、[DNV-RP-0510](https://www.dnv.com/digital-trust/recommended-practices/data-driven-applications-dnv-rp-0510/)、[DNV-RP-0513 simulation-model assurance](https://www.dnv.com/digital-trust/recommended-practices/simulation-models-assurance-dnv-rp-0513/)。RP/CG 是 assurance/classification 工具和要求入口，实际项目仍须由旗国、主管机关或认可组织按适用范围接受。

**IMO。** 截至本研究日期，IMO 已于 2026 年 5 月通过非强制 MASS Code（MSC.595(111)，2026-07-01 生效）。官方 FAQ 要求说明船舶设计的 operating modes，采用 goal-based、risk-assessment 导向，明确安全运行条件及超出限制时的行动，并保留 master 的总体责任；ROC 需要按 robust SMS 评估/认证/运行。该 Code 主要适用于 SOLAS Chapter I 货船（通常 >500 GT 国际航行），但建议尽可能用于更小 MASS；2026 年 12 月进入 Experience-Building Phase，计划在 2030 年前通过强制 Code、2032 年生效。

来源：[IMO FAQ – Autonomous shipping](https://www.imo.org/en/mediacentre/hottopics/pages/autonomous-shipping.aspx)、[MSC 110 roadmap](https://www.imo.org/en/mediacentre/meetingsummaries/pages/msc-110th-session.aspx)。2025 年报中的“正在制定 MASS Code”应按当时日期理解；不能用旧年报替代 2026 年当前法规状态。

## 6. 对自主避碰工程的直接启发

### 6.1 把 WP4 安全边界落到 COLAV/SA 接口

建议把自治航行系统的安全论证对象拆成四个可审计接口：

1. **SA contract**：目标存在性、位置/速度/艏向不确定性、时间戳、延迟、track quality、误检/漏检、传感器健康和融合退化状态。
2. **CA contract**：遇险识别、COLREG/用例规则解释、候选动作、风险指标、DCPA/安全域、规划更新时间、动作持续性和恢复策略。
3. **Action-control contract**：期望航迹/速度到实际舵角/推力的延迟、饱和、跟踪误差、推进/电源可用性，以及实际是否达到 CA 假设。
4. **Supervisory/MRC contract**：风险超限、感知降级、动力/通信失效时，谁触发减速、停车、保持位置、回退模式、通知 ROC 和接管；触发到可安全干预的时间必须可验证。

这样可以把 WP4 的“风险—控制—验证”落到现有 COLAV 代码，而不是在 CA 外再放一份不可执行的安全说明。

### 6.2 感知性能需求应由系统结果反推

最小可行试验矩阵应对每个 encounter 类型、船型、海况、航速、地图/浅水边界和多船组合，系统性注入：

- radar/AIS/GNSS/camera/lidar 的噪声、偏差、延迟、丢包和时间不同步；
- track birth/death、误检、漏检、错误关联、目标行为不遵守 COLREG；
- ownship 导航、推进、舵角、速度跟踪和通信的降级；
- ENC/grounding、风浪流和传感器健康状态变化。

每次试验至少保留 CPA/DCPA 分布、碰撞/搁浅、STL/规则 robustness、显著航向/速度变化、规划重算次数、任务完成率、MRC 触发率、人工接管余量和恢复情况。然后以“在目标风险和任务边界内的最坏/高分位表现”反推 SA 允许误差，而不是以孤立传感器 benchmark 代替系统安全。

ESREL/JPCS 两篇 2025 论文已经在低保真环境中演示这条方法可运行；论文也明确需要真实传感器统计、复杂 tracker/fusion、grounding 和 adversarial traffic 才能成为更强的证据。

### 6.3 把降级模式设计成可验证状态机

WP4 的 MRC、fail-to-safe、risk-aware mode switching 和 MA2 的实际边界事件共同说明，降级不能是“异常时调用一个 emergency stop”这么简单。至少应定义：

```text
NORMAL_AUTONOMY
  → MONITORED_DEGRADATION（风险/感知质量下降但仍可控）
  → RESTRICTED_AUTONOMY（限速、限域、保守 COLAV）
  → MINIMUM_RISK_CONDITION（停车/DP/锚泊/保持安全航向）
  → ROC_REMOTE_CONTROL / ONBOARD_MANUAL
  → RECOVERY 或 ABORT
```

每个转移要有输入、延迟、责任方、允许动作、退出条件和日志。对于“目标被误检”“目标暂时丢失”“GNSS/AIS 不可信”“雷达失效”“推进器失去冗余”“通信断链”分别定义行为，不要让统一 fallback 隐藏不同后果。

### 6.4 验证层级要与宣称匹配

| 层级 | 可支持的结论 | 不能单独支持的结论 |
|---|---|---|
| 低保真闭环/单元仿真 | 接口、规则、风险趋势、故障逻辑、参数敏感性 | 实船传感器/动力学真实性、运营安全 |
| 高保真/传感器仿真 | 动力学/海况/感知算法的开发和场景覆盖 | 未验证模型的等价性、所有 ODD 的安全 |
| HIL/模型水池 | 实时接口、控制时序、部分物理响应和硬件故障 | 缩比到全尺寸的直接等价 |
| MA1/MA2 受控海试 | 特定船、特定水域、特定传感器/航线的闭环和人工干预证据 | 无安全员、开放水域、其他船型的泛化 |
| NMA/旗国/DNV/RO 审查 | 在明确 CONOPS、ODD、船型和文件包下的批准/认证 | 未经审查的论文、TRL 或仿真分数本身 |

## 7. 结论：SFI AutoShip WP4 的完整发展链路

可以把 WP4 的产学研结合路线压缩为六个阶段：

1. **研究问题与风险语言**：用例、CONOPS、STPA/H-STPA/FTA/PHA、COLREG 法律解释和软件失效分类，把“安全”变成 hazard/UCA/RIF/要求。
2. **模型与控制原型**：BBN/online risk model、risk metric、risk-based path planning、SRC、MRC、mode switching、Legata/STL evaluator。
3. **闭环数字验证**：将 SA、CA、action control、动力学、ENC、环境和故障放在同一时钟；用噪声/偏差/失效扫描反推性能需求。
4. **数字—物理验证**：低/高保真模型、Stonefish/Unity、HIL、水池模型和统一控制接口；明确缩比、模型误差和不确定性边界。
5. **原型船与运营学习**：milliAmpere1 做控制/模型/海试，milliAmpere2 做城市客运工程原型和三周 public trial；用人工干预、false track、传感器/动力故障和 ROC 事件更新系统。
6. **外部 assurance/批准**：按 NMA CONOPS/HAZID/risk/gap/third-party verification、DNV class/assurance 工具、IMO MASS Code 和旗国要求形成独立审查证据包。

因此，SFI AutoShip 最值得复制的不是某个单点避碰算法，而是“研究模型—工程原型—受控运营—证据/规则—产业反馈”的闭环。对当前 MASS 项目，最先应建立的是：风险/模式状态机、可回放的 SA–CA–control 合同、故障注入与感知性能反推、场景/规则/轨迹证据链，以及清楚标注“仿真、HIL、实船、运营、认证”五类结论的报告体系。

## 8. 一手来源与本地材料索引

### 官方中心与监管

- [SFI AutoShip 总览（NTNU）](https://www.ntnu.edu/sfi-autoship)
- [Research & Innovation / WP 列表（NTNU）](https://www.ntnu.edu/sfi-autoship/research/)
- [WP4 Safety & Assurance（NTNU）](https://www.ntnu.edu/sfi-autoship/safety)
- [WP4 innovation leads（NTNU）](https://www.ntnu.edu/sfi-autoship/wp-4-innovation-leads)
- [Innovation leads 方法与成熟度（NTNU）](https://www.ntnu.edu/sfi-autoship/innovationleads)
- [Infrastructure / Shore Control Lab（NTNU）](https://www.ntnu.edu/sfi-autoship/infrastructure/)
- [News & Events（NTNU）](https://www.ntnu.edu/sfi-autoship/news/)
- [Annual Report 2025（NTNU PDF）](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2025.pdf/9dc32b39-98e6-93ff-fd55-695a9da0dbd0?t=1774619719616)
- [NMA RSV 12-2020](https://www.sdir.no/en/regelverk/circulars/guidance-in-connection-with-the-construction-or-installation-of-automated-functionality-aimed-at-performing-unmanned-or-partially-unmanned-operations/)
- [IMO FAQ – Autonomous shipping / MASS Code](https://www.imo.org/en/mediacentre/hottopics/pages/autonomous-shipping.aspx)
- [IMO MSC 110 MASS roadmap](https://www.imo.org/en/mediacentre/meetingsummaries/pages/msc-110th-session.aspx)

### 论文与技术原文

- [Maidana et al. 2023 – Risk-based path planning for collisions and groundings](https://doi.org/10.1016/j.oceaneng.2023.116417)
- [Kristensen et al. 2025 – Effect of risk metrics](https://doi.org/10.1016/j.oceaneng.2025.121937)
- [Dugan & Utne 2025 – AIS risk-influencing factors](https://doi.org/10.1016/j.ress.2025.111156)
- [Gomola et al. 2025 – Software failure taxonomy](https://doi.org/10.1177/1748006X241309170)
- [Kristensen et al. 2024 – Extended STPA/STPA-Sec](https://doi.org/10.1080/20464177.2024.2315646)
- [Johansen & Utne 2024 – Human-autonomy SRC](https://doi.org/10.1080/20464177.2024.2319369)
- [Hagen et al. 2023 – Safety and COLREG evaluation](https://doi.org/10.1016/j.oceaneng.2023.115991)
- [Løvoll et al. 2025 – CA robustness → SA requirements](https://doi.org/10.3850/978-981-94-3281-3_ESREL-SRA-E2025-P3941-cd)
- [Morris et al. 2025 – COLREG compliance → SA requirements](https://doi.org/10.1088/1742-6596/3123/1/012010)
- [Gezer et al. – Digital-physical testbed](https://arxiv.org/abs/2505.06787)
- [Eide et al. 2025 – milliAmpere2 design and testing](https://doi.org/10.1115/1.4067370)
- [Lee & Kim 2025 – Robust DRL under perception noise](https://doi.org/10.3850/978-981-94-3281-3_ESREL-SRA-E2025-P7222-cd)

### 本地交叉核对资料

- [Report_Autoship_2025 (1).pdf](</Users/marine/Documents/Paper/Report_Autoship_2025%20(1).pdf>)：WP4 印刷 pp. 38–46；TRL portfolio p. 52；COLAV simulator highlight pp. 53–54；组织 pp. 12–17；论文列表 pp. 71–74。
- [The Autonomous Urban Passenger Ferry milliAmpere2 – Design and Testing.pdf](</Users/marine/Documents/Paper/The%20Autonomous%20Urban%20Passenger%20Ferry%20milliAmpere2-%20Design%20and%20Testing.pdf>)：MA2 architecture、PHA、MRC、三周试航、25 次人工干预和 false-track 事件。
- [Digital-physical testbed for ship autonomy studies...pdf](</Users/marine/Documents/Paper/Digital-physical%20testbed%20for%20ship%20autonomy%20studies%20in%20the%20Marine%20Cybernetics%20Laboratory%20basin.pdf>)：C/S testbed、三层 simulation、Unity/ROC、44 个波浪验证、限制与未来工作。
- [From COLREG compliance to performance requirements...pdf](</Users/marine/Documents/Paper/From%20COLREG%20compliance%20to%20performance%20requirements%20for%20situational%20awareness%20systems%20in%20autonomous%20navigation%20systems.pdf>)：SA–CA–Action Control、GPS/radar degradation、STL、局限与未来故障模型。
- [Leveraging Collision Avoidance Robustness...pdf](</Users/marine/Documents/Paper/Leveraging%20Collision%20Avoidance%20Robustness%20to%20Establish%20Situational%20Awareness%20Requirements-%20A%20Closed%20Loop%20Simulator%20Approach.pdf>)：closed-loop 噪声扫描、DCPA/course-change 结果与局限。

本地资料和 `tmp/pdfs/` 提取文本只作为阅读/页码核对副本；外部主张以上述官方网页、DOI、论文原文和主管机关文件为准。
