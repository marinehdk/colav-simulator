# NTNU SFI AutoShip WP2 Digital Infrastructure：证据与发展链路

> 研究日期：2026-09-18。本文只研究 WP2 Digital Infrastructure；WP1 AutoRemote、WP3 ROC & Human Factors、WP4 Safety & Assurance 只在需要划清边界时引用。网页和论文是外部事实来源；`/Users/marine/Documents/Paper/Report_Autoship_2025 (1).pdf` 是本地核对副本。

## 1. 先给判断

WP2 不是“给船增加一个通信模块”，而是把自主船系统建模为一个跨船、岸基 RCC/ROC 和其他海上交通节点的分布式 maritime IoT。每个节点拥有不同传感器和局部视角，链路可能不对称，海况和天气使通信性能非平稳；WP2 的目标是按运行需要提供可靠、可保护的数据传输，并把分散信息处理成一致场景。

官方页面把 WP2 明确分成四个互相依赖的任务：

1. **Task 2.1：通信技术知识与方案比较**——自主船、RCC 和其他海上交通之间的通信。
2. **Task 2.2：无线电、雷达、协作通信、massive MIMO 和传感器融合。**
3. **Task 2.3：处理协作信息或系统提供信息的协议与原型。**
4. **Task 2.4：保护 2.1–2.3，针对 bitstream manipulation、spoofing、meaconing、jamming 等 cyber-physical attack。**

来源：[WP2 Digital infrastructure 官方页面](https://www.ntnu.edu/sfi-autoship/digital-infrastructure)，其四任务和目标见页面正文；同一结构也出现在 [SFI AutoShip Annual Report 20/21](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2020_web_ok.pdf/11d3c0b6-7351-5f28-a011-87072b9b46a1?t=1616779541167)，pp. 26–27。

截至 Annual Report 2025，WP2 的产出已经形成四条可辨认的技术线：

| 线 | 2025 年报给出的状态 | 与 MASS 避碰的关系 | 公开证据成熟度 |
|---|---|---|---|
| 通信性能模型 | maritime radio channel modelling，TRL 2 | 估计链路可用性、时延、吞吐和退化边界 | 有模型和论文；仍需更广泛海况测量与在线接口 |
| Radio Twin | ML-based communication performance prediction，TRL 2 | 提前选择通信链路/物理层参数，支持 graceful degradation | 处于研究原型阶段，非已部署船岸服务 |
| Ship–shore radar | conceptual ship-shore radar network，TRL 3 | 为近岸/港区低可观测目标提供岸基补充感知 | 论文和实测雷达数据有证据；“conceptual”仍是官方措辞 |
| 数据融合与闭环验证 | DNV 合作开发噪声、退化、故障下的 SA/CA simulator | 把感知误差传到避碰决策，评估 CPA、COLREG 与故障传播 | 可复现实验框架线索较多；没有公开完整产品化协议 |

来源：[Annual Report 2025 官方 PDF](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2025.pdf/9dc32b39-98e6-93ff-fd55-695a9da0dbd0?t=1774619719616)，WP2 pp. 28–32、创新组合 p. 52；[WP2 Innovation leads](https://www.ntnu.edu/sfi-autoship/wp-2-innovation-leads)。页码以本地 PDF 提取结果为准；网页抓取版本标题仍显示 “SFI Autoship årsrapport 2024”，正文标题为 Annual Report 2025。

## 2. WP2 的人员、项目和任务映射

官方当前 WP2 页面列出的 WP leader 是 Pierluigi Salvo Rossi（NTNU Department of Electronic Systems）；研究人员包括 Melih Akdag、Egil Sverre Eide、Torbjörn Ekman、Thor Inge Fossen、Manju James、Tor Arne Johansen、Kimmo Juhani Kansanen、Giacomo Melloni 和 Peter Keenan Morris。当前公开项目清单是：Collaborative collision avoidance、Real-time ship–shore radar、Data Fusion in Maritime IoT、Radio channel measurements and modelling、Radio Twin。

来源：[WP2 官方人员/项目清单](https://www.ntnu.edu/sfi-autoship/digital-infrastructure)。下面的任务映射是依据该清单、WP2 innovation leads 和年度报告的项目描述建立的；官方没有公开一份逐项标注“研究项目 = Task 2.x”的矩阵，因此标注为“主归属/交叉贡献”，避免把推断写成官方分配。

### Task 2.1：通信、链路和船岸连接

**Manju James / Kimmo Kansanen — Radio Twin：Digital Twin for Maritime Communication System Performance Prediction。**

官方 innovation lead 描述的问题是海况、船舶运动、海面散射和反射造成深衰落，确定性信道模型计算昂贵；方案是用实验和合成 channel data 训练机器学习模型，并用实验数据和已有文献验证。目标是预测信道性能、支持通信方式/物理层参数选择，并在链路恶化前切换或降级。年度报告 p. 32 进一步记录：2025 年已经用 Gaussian mixture 进行无线信道密度估计，正在实现算法；创新组合将该结果列为 ML-based communication performance prediction，TRL 2。

来源：[WP2 Radio Twin innovation lead](https://www.ntnu.edu/sfi-autoship/wp-2-innovation-leads#digital-twin-for-maritime-communication-system-performance-prediction)；[Annual Report 2025，Manju James，p. 32](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2025.pdf/9dc32b39-98e6-93ff-fd55-695a9da0dbd0?t=1774619719616)。

**Giacomo Melloni / Torbjörn Ekman — Radio channel measurements and modelling in maritime scenarios。**

官方 innovation lead 将关键物理因素列为 line-of-sight、specular reflection 和 diffuse scattering，并特别指出平静海面可能因强镜面反射而降低链路质量。目标是形成可嵌入船载设备的信道模型，以降低 outage probability、提高可靠性和容量。2025 年报 pp. 30–31 记录了海面大尺度散射场相位分布模型、EuCAP 2026 延伸论文，以及对 shadowing-aware mean/variance 和低计算量 diffuse-scattering 模型的后续工作。

来源：[WP2 Radio Channel measurements and modelling innovation lead](https://www.ntnu.edu/sfi-autoship/wp-2-innovation-leads#radio-channel-measurements-and-modelling)；[Giacomo Melloni 的 NTNU 发表记录](https://www.ntnu.no/ansatte/giacomme)；[Phase Distribution of the Large-Scale Scattered Field from the Sea Surface，EuCAP 2025，DOI 10.23919/EuCAP63536.2025.10999707](https://doi.org/10.23919/EuCAP63536.2025.10999707)。

一个有用的前置基线是 NTNU 参与的 [A Round Earth Loss Model and Small-Scale Channel Properties for Open-Sea Radio Propagation](https://doi.org/10.1109/TVT.2019.2929914)：该工作用挪威海域约 45 km、2 GHz 测量参数化并验证模型。它不是 2025 年 WP2 交付物，但说明 NTNU 的海上信道研究一直包含“模型—实测—链路性能”链路，而不只是抽象传播公式。

**通信架构和网络安全的前置基础。**

Ahmed Amro、Vasileios Gkioulos、Sokratis Katsikas 的 [Communication architecture for autonomous passenger ship](https://doi.org/10.1177/1748006X211002546) 使用 AADL 表达自主/远程控制客船架构，并用 GNS3 对场景和性能需求进行模拟验证。该论文由 NTNU 研究人员发表，是 WP2 船岸通信问题的直接前置证据；但当前 WP2 页面没有把 Amro 列入现行 WP2 研究人员清单，故本文把它标为“前置/交叉基础”，不把它冒充为 2025 年 WP2 项目。

### Task 2.2：雷达、协作感知和传感器融合

**Lukas Herrmann / Egil Eide — Real-time ship–shore radar。**

官方 innovation lead 给出的方案是：在多个岸基站点布置雷达，检测覆盖区域内的船舶并分发目标轨迹位置；动机是船载传感器在港口、近岸、低信噪比和小目标场景下不一定足够。2025 年报 pp. 28–29 进一步说明，研究重点是 shore-based radar network、sensor fusion、track-before-detect（TkBD）和实时性；Lukas Herrmann 于 2025 年 12 月完成 “Maritime Radar Detection and Tracking of Low-Observable Targets” 博士论文。2025 年官方圣诞 newsletter 还记录了四套雷达、两个站点的 Trondheim Fjord 网络建设，但网络存在本身不等于已经成为船舶运行链路。

来源：[Ship–shore radar network innovation lead](https://www.ntnu.edu/sfi-autoship/wp-2-innovation-leads#ship-shore-radar-network)；[Annual Report 2025，pp. 28–29](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2025.pdf/9dc32b39-98e6-93ff-fd55-695a9da0dbd0?t=1774619719616)；[SFI AutoShip Christmas Newsletter 2025](https://www.ntnu.edu/documents/1294735132/0/SFI%2BAutoShip%2BChristmas%2BNewsletter%2B2025.pdf/8acfcdd1-1b17-8cb6-afbf-f4466c65c7bb?t=1765895128900)。

公开算法证据如下：

* [Target Detection in Maritime Radar Tracking Based on Spatial Image Gradients](https://doi.org/10.1109/JSEN.2025.3569085)，[NTNU Open full text](https://hdl.handle.net/11250/3196521)：空间梯度检测器（SGBD）针对低 SNR 海上雷达图像，论文给出仿真、重尾/相关 clutter 分析和真实海上雷达数据验证。它具备较好的算法复现性，但需要兼容的原始雷达图像、坐标标定、海杂波参数和实时算力。
* [Histogram-Probabilistic Multi-Hypothesis Tracking with Integrated Target Existence](https://doi.org/10.1109/TAES.2025.3624188)，[arXiv preprint](https://arxiv.org/abs/2504.20526)：IE-PHPMHT 在 H-PMHT 上增加目标存在概率和 multi-Bernoulli birth，使目标数可变并把 track management 纳入模型。arXiv 版本便于实现公式，但最终 IEEE 版本访问可能受限；公开论文没有提供可直接部署的完整雷达采集/标定栈。
* [Track Initiation and Adaptive Target Birth in Existence-Based Poisson Histogram-PMHT](https://doi.org/10.1109/RadarConf2559087.2025.11205088)：论文摘要说明用 data-driven birth density 解决 TkBD 新轨迹启动，并以真实海上雷达数据补充数值仿真；公开会议页面和 DOI 足以确认结果，但没有看到完整公开代码/数据。

WP2 页面还保留 “cooperative, massive MIMO” 的任务表述，但在本次核对的 2025 年官方页面、年报和公开论文中，直接可验证的成果主要是海上信道散射/衰落模型、岸基雷达和 TkBD/传感器融合；没有找到一个已公开的船舶 massive-MIMO 海试原型。因此不能把“任务范围”写成“massive-MIMO 已完成部署”。

### Task 2.3：协作信息、协议和数据融合原型

**Melih Akdağ / Tor Arne Johansen — Collaborative collision avoidance / decision support。**

WP2 innovation lead 的 “A Decision Support System for Autonomous Ship Trajectory Planning” 目标是多目标优化产生多条候选路线，再按人类操作者的目标偏好排序；年度报告 p. 52 将 multi-objective trajectory planning tool 列为 WP2 TRL 5。它更接近“通信/信息被送到决策层后如何形成可解释候选路线”，不是底层网络协议。

同一研究线的 [A Decentralized Negotiation Protocol for Collaborative Collision Avoidance of Autonomous Surface Vehicles](https://doi.org/10.1109/TCST.2025.3619554) 公开描述了异步通信、DCOP、Distributed Stochastic Search、Monotonic Concession Protocol 和 fuzzy logic；论文声称用两个 reactive CA 算法、仿真和 field experiments 验证。可直接复现的部分是决策变量、约束和协商流程；没有公开完整的生产级消息 schema、发现/认证机制、丢包/重放策略、QoS 预算和跨厂商协议适配，因此不能把它等同于已标准化的 ship-to-ship protocol。

**Peter Keenan Morris / Pierluigi Salvo Rossi — Data Fusion in Maritime IoT。**

官方 innovation lead 描述的 simulator 可以配置传感器、环境、噪声、系统故障和多船场景，研究 fault propagation，并把 SA 输出送入 CA；还可比较 cooperative/non-cooperative vessel，并测试 adversarial 或 malicious behavior。年度报告 pp. 29–30 说明 2025 年与 DNV 合作把这个框架用于 SA/CA robustness、噪声/退化/故障和 Signal Temporal Logic，且开始支持协作自主船系统。

来源：[Data fusion in maritime IoT innovation lead](https://www.ntnu.edu/sfi-autoship/wp-2-innovation-leads#data-fusion-in-maritime-iot)；[From COLREG compliance to performance requirements for situational awareness systems in autonomous navigation systems](https://doi.org/10.1088/1742-6596/3123/1/012010)；[Leveraging Collision Avoidance Robustness to Establish Situational Awareness Requirements: A Closed Loop Simulator Approach](https://doi.org/10.3850/978-981-94-3281-3_ESREL-SRA-E2025-P3941-cd)；[Peter Morris 的 NTNU 发表/报告页面](https://www.ntnu.no/ansatte/petemorr)。

这条线的工程价值在于把“感知质量”接到“避碰后果”上：不是只给 radar/GPS 加噪声后看轨迹，而是通过闭环 CA 指标（如 CPA、碰撞风险和 COLREG 约束）反推 SA 的性能要求。论文/年报能够支持实验框架复现，但没有公开一套面向真实船岸系统的统一数据模型、时间同步、版本化回放格式和安全协议。

### Task 2.4：cyber-physical protection

WP2 官方任务范围明确包含 bitstream manipulation、spoofing、meaconing 和 jamming；这是对通信、雷达和协作信息链路的横向约束，不是单独的“IT 安全附录”。

公开安全证据主要来自 NTNU Gjøvik 相关研究线：

* [Communication and Cybersecurity Testbed for Autonomous Passenger Ship](https://doi.org/10.1007/978-3-030-95484-0_1) 说明了面向 autonomous passenger ship 的通信/网络安全 testbed、目标系统复制和评估流程；论文也列出缺失能力和后续工作。
* [Communication architecture for autonomous passenger ship](https://doi.org/10.1177/1748006X211002546) 给出 AADL 架构和 GNS3 性能验证。
* Ahmed Amro 的 [NTNU publication page](https://www.ntnu.edu/employees/ahmedwa) 列出 `Impact of cyber risk on the safety of the milliAmpere2 Autonomous Passenger Ship`（2020，DOI [10.1088/1757-899X/929/1/012018](https://doi.org/10.1088/1757-899X/929/1/012018)）、`Navigation Data Anomaly Analysis and Detection`（2022）、`Cyber risk management for autonomous passenger ships using threat-informed defense-in-depth`（2022）以及 2023 博士论文 [Communication and cybersecurity for autonomous passenger ferry](https://hdl.handle.net/11250/3064022)。

这些文献可作为 Task 2.4 的威胁建模、testbed 和异常检测前置基础；但当前 WP2 官方项目清单没有列出一个独立的 2025 Task 2.4 项目，也没有在公开资料中看到 bitstream/spoofing/meaconing/jamming 的海试攻击数据集、检测率/误报率、切换策略或认证协议。因此只能报告“有安全研究链和任务定义”，不能报告“Task 2.4 已经形成可部署安全栈”。

## 3. milliAmpere、船岸网络、ROS 和 co-simulation：哪些是实证，哪些不能归 WP2

### 3.1 milliAmpere1/2 的船岸链路是工程实证，但不等于 WP2 交付物

两篇 NTNU/AutoFerry 论文给出了很有价值的系统边界：

* [milliAmpere: An Autonomous Ferry Prototype](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3039489)（JPCS 2311, 012029, DOI [10.1088/1742-6596/2311/1/012029](https://doi.org/10.1088/1742-6596/2311/1/012029)）描述了多传感器、ROS 节点 publish/subscribe、避碰/跟踪/定位和 Shore Control Lab。
* [The Autonomous Urban Passenger Ferry milliAmpere2: Design and Testing](https://doi.org/10.1115/1.4067370) 描述了 2022 公共试运营和 2025 论文中的通信架构：ROC 与船通过 4G/5G 连接，DP 系统另有 proprietary C-band 5.8 GHz 链路；三张私有网络分别承担高容量 5G、备份 4G 和 DP 远程控制，base station、ROC、milliAmpere2 和 data center 互联，data center 提供存储和加密访问。

这些是“系统已经被连起来并在运营/试验中使用”的强证据，但论文属于 AutoFerry/milliAmpere 系统与使用案例，不能据此声称 WP2 的每个 Task 已经在 milliAmpere2 上验收。尤其是 4G/5G/C-band 网络和 encrypted data server 是运行架构事实，不是 WP2 研究协议、Radio Twin 或 cyber-physical attack evaluation 的充分证据。

### 3.2 ROS 是内部集成底座，不是 WP2 的研究边界

milliAmpere 论文表明船上软件采用 ROS 的原子节点和 publish/subscribe 通信；Annual Report 2025 的 WP1 mission-planning 页面还写明研究者修改了 ROS-based milliAmpere source code，以支持实时 mission planning。这说明 ROS 适合作为船内算法/传感器组件的工程胶水，但 WP2 关注的是跨节点、跨链路的数据转移、协作信息处理和安全约束。不能把“用了 ROS”写成 WP2 的通信协议成果，也不能把 ROS topic 自动视为可跨船岸使用的安全接口。

来源：[milliAmpere NTNU Open](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3039489)；[WP1 AutoRemote 官方页面](https://www.ntnu.edu/sfi-autoship/autoremote)。

### 3.3 Gemini、FMI/OSP 是可复用的仿真/协同仿真证据，归属仍需分开

* [Autoferry Gemini: a real-time simulation platform for electromagnetic radiation sensors on autonomous ships](https://doi.org/10.1088/1757-899X/929/1/012032) 使用 Unity、GPU compute shaders 和 gRPC 为雷达、激光雷达、可见光/红外相机提供实时模拟；[NTNU Shore Control Lab 论文](https://doi.org/10.1088/1742-6596/2311/1/012030) 说明 Gemini 用于测试船上 autonomy/sensor/actuator/control、远程操作员和 HMI。
* [Open Simulation Platform 的 milliAmpere co-simulation demonstrator](https://open-simulation-platform.github.io/cosim-demo-app/milliAmpere) 将原始 ROS 节点的 control/plant core 包装成八个 FMI 2.0 FMU（mission manager、guidance、navigation、DP、thrust allocation、vessel、wind），支持 FMPy 和 OSP/libcosim、headless 和浏览器运行。该页面还明确说模型/FMUs 需要 milliAmpere repository 权限，因而不能把页面当作完整开源数据/代码交付。

这两类材料适合证明“ROS/Unity/FMI/OSP 可以把船上栈拆成可重复实验的仿真组件”，并为 WP2 的链路退化、传感器数据损坏、消息延迟和故障注入提供集成位置；它们本身属于 AutoFerry、WP1、WP4/测试基础设施或平台文档，不能自动归为 WP2 的 Radio Twin 或 Task 2.3 协议原型。

## 4. “数字孪生”边界：WP1、WP2、WP4 和仿真器不是同一个东西

| 名称 | 主要对象 | 官方/论文证据 | 能否归 WP2 |
|---|---|---|---|
| WP1 Digital Twin for Situational Awareness and Optimal Control | 船舶/环境状态、动力学、感知、预测安全滤波和控制；目标是用实时数据和自适应模型支撑船舶决策 | [WP1 官方页面](https://www.ntnu.edu/sfi-autoship/autoremote)；Annual Report 2025 p. 71 列出 `Digital twin syncing for autonomous surface vessels using reinforcement learning and nonlinear model predictive control` | **否，主归 WP1** |
| WP2 Radio Twin | 海上无线信道、散射/衰落、SNR、data rate/latency 和链路性能；输出用于链路选择与 graceful degradation | [WP2 Radio Twin innovation lead](https://www.ntnu.edu/sfi-autoship/wp-2-innovation-leads#digital-twin-for-maritime-communication-system-performance-prediction)；Annual Report 2025 p. 32 | **是，WP2 的通信性能 twin** |
| WP2 Data Fusion simulator | 传感器噪声、SA/CA、系统故障、环境和多船闭环；用于性能和 V&V | [WP2 Data Fusion innovation lead](https://www.ntnu.edu/sfi-autoship/wp-2-innovation-leads#data-fusion-in-maritime-iot)；Annual Report 2025 pp. 29–30 | **是，WP2 测试/验证框架；不是 vessel digital twin** |
| WP4 Safety digital twin / digital-physical testbed | 安全验证、风险、safe control 和跨 fidelity 测试链 | [WP4 官方页面](https://www.ntnu.edu/sfi-autoship/safety)；Annual Report 2025 p. 52 | **否，主归 WP4** |
| Autoferry Gemini / FMI-OSP | 传感器、控制栈、操作员和船舶动态的实时模拟/协同仿真平台 | [Gemini DOI](https://doi.org/10.1088/1757-899X/929/1/012032)；[OSP milliAmpere demo](https://open-simulation-platform.github.io/cosim-demo-app/milliAmpere) | 平台支撑，**不因使用了通信或 sensor data 就自动变成 WP2** |

最容易发生的误读是把 “Radio Twin” 和 “Digital Twin for Situational Awareness and Optimal Control” 都简称为 digital twin。前者预测通信信道，后者同步/估计船舶与环境状态；一个输出链路质量，另一个进入感知、预测和控制。对避碰系统而言，二者应通过明确的接口连接：

```text
船舶/岸基状态、传感器和环境
          │
          ├─ WP1：船舶/环境 twin → SA、预测、规划、控制
          │
          ├─ WP2 Task 2.1/2.2：通信/雷达/信道模型 → 数据可用性、时延、质量、目标轨迹
          │
          └─ WP2 Task 2.3：协议/数据融合 → SA/CA 输入与协作意图
                         │
                         └─ WP4：风险、故障、攻击和 V&V 证据
```

## 5. 论文和原型的可实施性边界

### 5.1 当前可以直接借鉴的实现切片

1. **船岸通信抽象**：从 AADL/GNS3 架构和 milliAmpere2 的 5G/4G/C-band 三链路得到链路类别、控制流与高带宽传感器流的分离原则。
2. **通信性能仿真**：把 sea-state、surface scattering、shadowing、deep fade、SNR、latency 和 packet loss 作为链路模型输入；先复现实测条件，再接 Radio Twin 的 GMM/ML 预测。
3. **岸基雷达补充感知**：先用公开 SGBD/TBD 论文实现离线 replay，再接多站时间同步、目标坐标变换和轨迹分发；不要先假设它已经是可靠的船上避碰输入。
4. **闭环 SA→CA 测试**：用 Morris/DNV 框架的噪声、退化、故障和多船场景，把感知质量映射到 CPA、COLREG 和碰撞风险；这更适合验证/需求推导，而不是作为船上实时模块直接替换。
5. **协作避碰消息层**：从 Akdağ 的协商流程抽取意图、候选动作、约束、超时和 concession 状态，再自行定义版本化 schema、身份认证、重放保护、丢包策略和安全降级。
6. **ROS/FMI/OSP 接缝**：在船内 ROS topic 与船岸外部消息之间建立显式 adapter；用 FMI/OSP 做可重复的时延、丢包、降级和故障注入，不把内部 ROS topic 直接暴露给无线链路。

### 5.2 公开证据仍不能支持的结论

* 没有公开证据证明 WP2 已形成跨厂商、可部署的 ship-to-ship/ship-to-RCC 通信协议标准。
* 没有公开完整的 WP2 Task 2.4 攻击注入、检测、隔离、恢复和验收指标；“任务声明有 spoofing/jamming”不等于已经完成安全闭环。
* 没有公开 Radio Twin 的完整训练数据、模型权重、推理 API、在线切换策略和不同海况的泛化误差。
* 没有公开 ship–shore radar network 的连续运行可用性、时间同步误差、轨迹延迟/丢失统计、跨站数据格式和直接馈入 CA 的验收结果。
* 论文的仿真、field experiment、milliAmpere 试航、milliAmpere2 公共试运营属于不同证据层级；不能因为它们都围绕 AutoShip/AutoFerry，就把局部实验写成完整 MASS 系统验收。

## 6. 对避碰系统工程化的直接启示

WP2 最值得复制的不是某一个网络或雷达算法，而是把“信息可用性”当作避碰系统的显式输入和可验证契约：

```text
链路/传感器/岸基雷达事实
  → 数据质量、时间戳、置信度、延迟、完整性、攻击状态
  → SA/目标轨迹与协作意图
  → CA/规划行为
  → CPA、COLREG、任务完成、降级和最小风险状态
```

因此，针对自有 MASS/COLAV 平台，至少应为每条外部信息保存 `source_id`、采样/发送/接收时间、坐标参考系、质量/置信度、链路状态、完整性/认证状态和失效原因；同时为每种通信/感知退化规定 CA 的行为边界。WP2 的公开成果可以支撑“模型和闭环测试”的研究路线，但生产接受仍需要本地数据、协议、攻击场景、时序证据和海试验证。

## 7. 来源索引

### 官方 WP、年报和项目结构

* [SFI AutoShip 总览](https://www.ntnu.edu/sfi-autoship)
* [Research – SFI AutoShip](https://www.ntnu.edu/sfi-autoship/research/)
* [WP2 Digital infrastructure](https://www.ntnu.edu/sfi-autoship/digital-infrastructure)
* [WP2 Innovation leads](https://www.ntnu.edu/sfi-autoship/wp-2-innovation-leads)
* [Innovation leads 说明及 TRL/KTH readiness 口径](https://www.ntnu.edu/sfi-autoship/innovationleads)
* [Annual Report 2025（官方 PDF）](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2025.pdf/9dc32b39-98e6-93ff-fd55-695a9da0dbd0?t=1774619719616)
* [Annual Report 20/21（官方 PDF）](https://www.ntnu.edu/documents/1294735132/0/Report_Autoship_2020_web_ok.pdf/11d3c0b6-7351-5f28-a011-87072b9b46a1?t=1616779541167)
* [WP1 AutoRemote](https://www.ntnu.edu/sfi-autoship/autoremote)
* [WP4 Safety & Assurance](https://www.ntnu.edu/sfi-autoship/safety)

### 通信、雷达、数据融合和协作避碰

* [Communication architecture for autonomous passenger ship](https://doi.org/10.1177/1748006X211002546)
* [A Round Earth Loss Model and Small-Scale Channel Properties for Open-Sea Radio Propagation](https://doi.org/10.1109/TVT.2019.2929914)
* [Phase Distribution of the Large-Scale Scattered Field from the Sea Surface](https://doi.org/10.23919/EuCAP63536.2025.10999707)
* [Target Detection in Maritime Radar Tracking Based on Spatial Image Gradients](https://doi.org/10.1109/JSEN.2025.3569085)；[NTNU Open full text](https://hdl.handle.net/11250/3196521)
* [Histogram-Probabilistic Multi-Hypothesis Tracking with Integrated Target Existence](https://arxiv.org/abs/2504.20526)；[IEEE DOI](https://doi.org/10.1109/TAES.2025.3624188)
* [Track Initiation and Adaptive Target Birth in Existence-Based Poisson Histogram-PMHT](https://doi.org/10.1109/RadarConf2559087.2025.11205088)
* [A Decentralized Negotiation Protocol for Collaborative Collision Avoidance of Autonomous Surface Vehicles](https://doi.org/10.1109/TCST.2025.3619554)
* [From COLREG compliance to performance requirements for situational awareness systems in autonomous navigation systems](https://doi.org/10.1088/1742-6596/3123/1/012010)
* [Leveraging Collision Avoidance Robustness to Establish Situational Awareness Requirements](https://doi.org/10.3850/978-981-94-3281-3_ESREL-SRA-E2025-P3941-cd)

### 船岸实证、网络安全和仿真平台

* [milliAmpere: An Autonomous Ferry Prototype](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3039489)
* [The Autonomous Urban Passenger Ferry milliAmpere2: Design and Testing](https://doi.org/10.1115/1.4067370)
* [NTNU Shore Control Lab: Designing Shore Control Centres in the Age of Autonomous Ships](https://doi.org/10.1088/1742-6596/2311/1/012030)
* [Autoferry Gemini](https://doi.org/10.1088/1757-899X/929/1/012032)
* [Communication and Cybersecurity Testbed for Autonomous Passenger Ship](https://doi.org/10.1007/978-3-030-95484-0_1)
* [Ahmed Amro NTNU publications](https://www.ntnu.edu/employees/ahmedwa)
* [Open Simulation Platform milliAmpere FMI/OSP demonstrator](https://open-simulation-platform.github.io/cosim-demo-app/milliAmpere)

## 8. 证据限制

1. 官方 WP2 页面是当前项目和人员总表，不是逐任务完成报告；任务归属关系中，除页面明示的项目外，本文只做“主归属/交叉贡献”判断。
2. Annual Report 2025 是年度总结，不提供每个模型、代码、数据集和现场运行 KPI；TRL 是 SFI innovation portfolio 的成熟度标记，不等于船级社批准或 MASS 运行许可。
3. 部分论文有公开全文，部分只有摘要/DOI；公开论文可证明研究方法和实验设置，不能自动证明源代码、数据、实时性能或生产安全。
4. milliAmpere1/2、Shore Control Lab、Gemini、FMI/OSP 是重要的工程验证基础，但其论文属于 AutoFerry/船舶系统/测试平台研究；本文没有把这些邻近成果全部归入 WP2。
5. 2026 年后研究仍在进行，本文只记录截至研究日可访问的官方页面和公开论文，不推断未公开的后续交付物。
