# NTNU/Maritime Robotics 数字孪生、模型同步与实船辨识证据

日期：2026-09-17  
范围：本地三篇论文逐页核对；补充论文 DOI/官方论文页、Maritime Robotics Otter 产品规格、Telemetron 实船验证资料。  
目标：判断论文中的“数字孪生同步”到底同步了什么，区分仿真证据与实船证据，并为 Colav-Simulator -> ROS2 L2-L5 -> 45 m FCB 的三步路线设计可审计的数据、回放和校准边界。

## 结论先行

1. **Berg 等 2025 的“sync”是仿真内 DRL 参数更新机制，不是已验证的物理船-数字孪生在线闭环。** DRL 在数字孪生环境中更新 NMPC 权重，或更新 Telemetron 模型的质量矩阵和非线性阻尼矩阵；论文结果来自随机仿真 episode 与模拟环境扰动，作者明确说实际世界验证仍需开展。[本地 PDF：Berg 等，pp. 1, 6-7, 14-17](../../paper/Digital%20twin%20syncing%20for%20autonomous%20surface%20vessels%20using%20reinforcement%20learning%20and%20nonlinear%20model%20predictive%20control.pdf)；[Scientific Reports DOI](https://doi.org/10.1038/s41598-025-93635-9)

2. **Menges 等 2024 的 Unity DT 解决的是感知、目标跟踪、what-if 和安全过滤。** RL 产生名义控制，PSF/NMPC 以约束优化对其做最小安全修正；论文明确写出 DT 尚未连接真实 ASV，闭环没有建立。[本地 PDF：Menges 等，pp. 2-9](../../paper/DIGITAL%20TWIN%20OF%20AUTONOMOUS%20SURFACE%20VESSELS%20FOR%20SAFE%20MARITIME%20NAVIGATION%20ENABLED%20THROUGH%20PREDICTIVE%20MODELING%20AND%20REINFORCEMENT%20LEARNING.pdf)；[arXiv:2401.04032](https://arxiv.org/abs/2401.04032)；[OMAE 2024 DOI](https://doi.org/10.1115/OMAE2024-122628)

3. **Kandemir 等 2025 才提供“真实航行数据 -> 动力学模型 -> DT 仿真验证”的证据链。** 数据来自真实 Otter USV 的 GNSS/IMU/控制输入等日志，使用 4 次直线和 4 次圆周机动做 3-DOF SINDy 辨识，再以留出机动和 k-fold 验证；没有证明真实船上已部署 COLAV/RL，也没有证明 45 m 船的可迁移性。[本地 PDF：Kandemir 等，pp. 1-12](../../paper/SINDy-based%20modeling%20of%20an%20uncrewed%20surface%20vessel%20with%20experimental%20validation.pdf)；[Elsevier DOI](https://doi.org/10.1016/j.apor.2025.104825)

4. **三篇论文共同支持“模型驱动 + 数据校准 + 可重复仿真”的工程路线，不支持把小船模型系数直接搬到 45 m FCB。** Otter 官方规格为 2,000 mm x 1,065 mm x 1,080 mm、干重 62 kg、最高 4.5 kn；Telemetron 的实船验证资料为 8.45 m x 2.71 m、1,675 kg、34 kn。它们都与 45 m FCB 处于不同质量、惯量、推进、传感器和环境尺度。[Otter 官方规格](https://www.maritimerobotics.com/otter)；[Telemetron 实船验证 DOI](https://doi.org/10.1002/rob.21919)

5. **第三步应把“船长做了什么”和“船长想做什么”分成两个数据层。** 记录的舵/车/航向/速度命令是 observed action；intent 只能作为带来源、时间窗和置信度的推断标签。开放环决策回放用于比较算法输出与当时真实命令；闭环反事实回放用于问“如果执行另一策略会怎样”，不能倒推为船长真实意图。

## 1. 证据来源与物理/仿真边界

| 来源 | 论文对象与方法 | 是否有真实船数据 | 可直接支持的结论 |
|---|---|---|---|
| Berg, Menges, Tengesdal, Rasheed, *Scientific Reports* 15, 9344 (2025) | Telemetron 3-DOF 模型；DRL 调 NMPC 权重或 M、D 参数；ENC、风浪扰动仿真 | **没有实船闭环证据**；数据集仅称可向通讯作者索取 | 证明仿真内 DRL-NMPC 能调参、在给定 ground truth 附近估计参数；不证明真船在线同步 |
| Menges, Von Brandis, Rasheed, arXiv v2 / OMAE 2024 | Unity DT；AIS + 合成 LiDAR；KF 目标跟踪；PPO + PSF | **无真实 ASV 闭环**；AIS/天气为框架数据流，LiDAR 结果为合成点云 | 证明 DT 的预测、what-if、RL 安全过滤和目标跟踪概念；不证明物理模型校准 |
| Kandemir, Coates, Hasan, *Applied Ocean Research* 165 (2025) 104825 | Otter 3-DOF；SINDy 稀疏辨识；直线/圆周实船机动 | **有真实 Otter 试验数据**，并与 DT 模型比较 | 证明真实小型 USV 数据可辨识出可解释的稀疏动力学；暴露噪声、激励覆盖和积分漂移问题 |

DT 能力等级来自第二篇论文：0 standalone、1 descriptive、2 diagnostic、3 predictive、4 prescriptive、5 autonomous。其定义要求 Level 5 由 DT 到物理系统的环路闭合；第二篇工作只扩展到 Level 3/4 附近，明确没有闭环。[本地 PDF p. 3-4, 9](../../paper/DIGITAL%20TWIN%20OF%20AUTONOMOUS%20SURFACE%20VESSELS%20FOR%20SAFE%20MARITIME%20NAVIGATION%20ENABLED%20THROUGH%20PREDICTIVE%20MODELING%20AND%20REINFORCEMENT%20LEARNING.pdf)

## 2. 论文一：DRL-NMPC 参数同步到底做了什么

### 2.1 动力学与 NMPC 执行闭环

论文使用 3-DOF 平面模型：

- 位姿 `eta = [x_s, y_s, psi]`，体坐标速度 `nu = [u, v, r]`；状态 `x = [eta, nu]`。
- 动力学为 `M nu_dot + D(nu) nu + C(nu) nu = tau + tau_d`，控制输入为 surge thrust 和 yaw moment，环境扰动为风、浪、流等合力/力矩。
- Telemetron 阻尼写成 `D(nu) = D_l + D_q(|nu|) + D_c(nu^T nu)`；Coriolis 矩阵由质量矩阵 `M` 的元素计算。
- NMPC 用 direct multiple shooting 求解带状态、输入、软约束和扰动观测器输出的 OCP；每个时间步只施加第一项控制，再用新状态重解。这是执行器闭环，属于仿真控制闭环。[本地 PDF pp. 3-5, 6-7](../../paper/Digital%20twin%20syncing%20for%20autonomous%20surface%20vessels%20using%20reinforcement%20learning%20and%20nonlinear%20model%20predictive%20control.pdf)

这里的闭环是“NMPC <-> 仿真 DT”，不是“实船传感器 <-> DT”。图 2 的结构显示 DT 给出 observation，NMPC 给出 control，DRL 给出 action，reward 来自仿真执行结果；图示没有物理船数据入口。[本地 PDF p. 7，图 2](../../paper/Digital%20twin%20syncing%20for%20autonomous%20surface%20vessels%20using%20reinforcement%20learning%20and%20nonlinear%20model%20predictive%20control.pdf)

### 2.2 DRL 的两个角色

| 模式 | DRL observation | DRL action | 仍由谁执行控制 | 论文中的含义 |
|---|---|---|---|---|
| NMPC tuning | `x`、CTE、期望航向/速度、航向误差、速度误差 | 在预设上下界内设置 `Q、R、W` | NMPC | 找到更好的 cost 权重；初始上下界来自数字孪生中人工调过的参数，目的是限制不安全探索 |
| Model parameter identification | 同一 observation/reward | 设置 `M` 与非线性 `D`；`C` 由 `M` 计算 | NMPC | 在给定仿真 ground truth 和动作范围内寻找模型参数，使闭环 reward/跟踪表现最好 |

模型参数更新式是 `M_new = M_original + alpha (a_M ⊙ M_original)`、`D_new = D_original + alpha (a_D ⊙ D_original)`。`a_M/a_D` 在 `[-1,1]` 归一化；某些原始 `D_q/D_c` 元素为零，作者把它们在 action space 中放大 1000 倍；`alpha=1` 造成 NMPC solver error，最后降到 `alpha=0.25` 才能训练收敛。[本地 PDF pp. 6-7](../../paper/Digital%20twin%20syncing%20for%20autonomous%20surface%20vessels%20using%20reinforcement%20learning%20and%20nonlinear%20model%20predictive%20control.pdf)

这是一种**受限的策略搜索/在线仿真参数调优**。它不是从实船日志做系统辨识的标准流程：论文没有给出实船传感器、时间同步、测量残差、参数后验或物理试验数据摄取接口。

### 2.3 仿真证据与边界

- 仿真使用论文引用的 COLAV framework，包含 ENC、船舶模型、风浪物理扰动；NMPC horizon `N=10`，`Delta t=1 s`。
- 5 million 个仿真时间步约耗时一天；模型参数估计训练用 PPO 10 million time steps。测试为 100 个按同一场景生成配置、不同随机种子的 episode。
- 作者报告 DRL 调参在无扰动/有扰动/交叉会遇仿真中降低 CTE、提高到达率；表 5 的参数误差是相对于**仿真 ground truth**，不是实船辨识真值。结论中的“最大相对参数误差低于 10%、平均约 2.6%”也应按此边界解读。[本地 PDF pp. 7-15](../../paper/Digital%20twin%20syncing%20for%20autonomous%20surface%20vessels%20using%20reinforcement%20learning%20and%20nonlinear%20model%20predictive%20control.pdf)
- 论文数据可向通讯作者合理请求；结尾明确写明还需要 real-world validation tests。[本地 PDF pp. 15-18](../../paper/Digital%20twin%20syncing%20for%20autonomous%20surface%20vessels%20using%20reinforcement%20learning%20and%20nonlinear%20model%20predictive%20control.pdf)

因此，对 Colav-Simulator 的可借鉴点是“先在安全仿真中调 cost、辨识候选参数、保持参数动作有界”，而不是把它作为已完成的真船同步方案。

## 3. 论文二：Unity DT、目标跟踪与 PSF 的真实作用

### 3.1 DT 的输入和能力层级

论文在 Unity 中组合：

- Trondheim Fjord 真实 3D elevation map、船 CAD 模型和 Unity game engine；Level 0 是可视化 DT。
- Level 1 加入非线性船舶/推进器动力学、实时 AIS 和天气数据。AIS 消息间隔不固定，消息之间用外推补齐；天气包含风速、风向、温度、气压等，图 3 标注约 1 km2 分辨率、12 个变量、约 3 min 更新。
- Level 2 的外部诊断使用非线性 disturbance observer 估计风、浪、流造成的环境力；内部发动机状态监测只作为概念图，未集成到该 DT。
- Level 3/4 由目标轨迹预测、风险分析和 PSF 支撑；Level 5 要求 DT 与真实系统闭环，但本论文没有做到。[本地 PDF pp. 2-4, 9](../../paper/DIGITAL%20TWIN%20OF%20AUTONOMOUS%20SURFACE%20VESSELS%20FOR%20SAFE%20MARITIME%20NAVIGATION%20ENABLED%20THROUGH%20PREDICTIVE%20MODELING%20AND%20REINFORCEMENT%20LEARNING.pdf)

### 3.2 目标跟踪与传感器融合

对其他船舶，通常没有质量和水动力参数，因此论文不用完整船舶模型，而采用 constant-velocity 目标模型：`x_kin = [x_s, y_s, x_dot_s, y_dot_s]`。AIS 与 LiDAR 各自经过 KF 预测/校正，再做 late fusion：根据各自 Kalman gain/协方差加权；AIS 约每分钟一次，LiDAR 高频到达，只有注册到 AIS 时才融合。LiDAR 点云在 Unity 中是合成且带噪的，先做稳定椭圆拟合，再估计目标形状/姿态。[本地 PDF pp. 5-6, 8](../../paper/DIGITAL%20TWIN%20OF%20AUTONOMOUS%20SURFACE%20VESSELS%20FOR%20SAFE%20MARITIME%20NAVIGATION%20ENABLED%20THROUGH%20PREDICTIVE%20MODELING%20AND%20REINFORCEMENT%20LEARNING.pdf)

这对 FCB 的启示是：目标数据应保存每个来源的原始观测、时间戳、协方差和过滤后状态，不能只保存“融合后的目标船轨迹”。否则无法复盘 AIS 延迟、雷达/视觉误差或融合权重对 COLAV 决策的影响。

### 3.3 RL 与 PSF 的职责边界

- RL/PPO 输出名义动作 `u_L`，学习路径跟踪和 COLAV reward。
- PSF 解一个 NMPC 风格 OCP，最小化 `||u_0 - u_L||_W^2`，同时满足动力学、状态/输入边界、每步安全距离、终端安全距离和控制不变椭球集合；输出最小修改的安全动作 `u_0`。
- `delta_u = u_L - u_0` 被反馈进 RL reward，表示安全过滤介入程度。PSF 是安全屏障/执行前验证器，不是模型同步器，也不是船长意图识别器。
- 论文比较 PPO、PPO+PSF、PPO+带移动目标信息的 PSF；只有最后一个设置在训练期间碰撞率保持为 0。[本地 PDF pp. 6-9](../../paper/DIGITAL%20TWIN%20OF%20AUTONOMOUS%20SURFACE%20VESSELS%20FOR%20SAFE%20MARITIME%20NAVIGATION%20ENABLED%20THROUGH%20PREDICTIVE%20MODELING%20AND%20REINFORCEMENT%20LEARNING.pdf)

开放海域跟踪预测相对准确，靠岸场景出现不稳定；作者将其归因于 constant-velocity 假设或 Unity 图形/物理/API 集成限制。结果部分最后明确写出“DT 未连接真实 ASV，loop 尚未闭合”。[本地 PDF p. 9](../../paper/DIGITAL%20TWIN%20OF%20AUTONOMOUS%20SURFACE%20VESSELS%20FOR%20SAFE%20MARITIME%20NAVIGATION%20ENABLED%20THROUGH%20PREDICTIVE%20MODELING%20AND%20REINFORCEMENT%20LEARNING.pdf)

## 4. 论文三：SINDy 的实船数据、辨识输入与可迁移边界

### 4.1 实船对象与数据

论文使用 Maritime Robotics Otter。论文报告两台 AC motor、每台/系统描述最高 125 N 推力、onboard computer，以及 GNSS、AIS、VHF、4G、WiFi、高清相机；IMU 与 GNSS 融合用于更平滑的位置、速度和航向估计。[本地 PDF pp. 3-4](../../paper/SINDy-based%20modeling%20of%20an%20uncrewed%20surface%20vessel%20with%20experimental%20validation.pdf)

论文没有给出 Otter 的尺寸和干重；制造商当前官方页面给出 2,000 mm 长、1,065 mm 宽、1,080 mm 高、干重 62 kg、最高 4.5 kn、载荷 30 kg，并将其定位为 sheltered/coastal waters 的轻型 USV。[Maritime Robotics: The Otter](https://www.maritimerobotics.com/otter)

实验设计有意激励不同运动模态：

- 4 次不同速度的直线机动，主要激励纵向运动。
- 4 次不同半径/速度的圆周机动，激励横向和耦合运动。
- 直线机动中加入不同频率/持续推力/阶跃输入；机动由人工给出，存在小幅不完美。
- 3-DOF 状态为 `u, v, r`；控制输入为 surge thrust `T_u` 与 yaw torque `T_r`。候选 library 为一阶多项式、二阶多项式、physics-informed custom library `[u,v,r,T_u,T_r,u*r,v*r,r^2]`。[本地 PDF pp. 2-6](../../paper/SINDy-based%20modeling%20of%20an%20uncrewed%20surface%20vessel%20with%20experimental%20validation.pdf)

### 4.2 SINDy 机制

SINDy 使用时序状态 `X` 和数值导数 `X_dot` 构造候选函数库 `Theta(X)`，再以稀疏回归求 `X_dot = Theta(X) Xi`。L1 正则或 sequentially thresholded least squares 选择少量有效项，最终把显式稀疏方程嵌入 physics-based DT。优点是可解释、数据量相对小、可以把已有水动力知识写进 library；缺点是候选库遗漏的耦合、时延或 hysteresis 不会被发现，数值微分对噪声敏感，固定模型会随工况变化失配。[本地 PDF pp. 5-6, 11-12](../../paper/SINDy-based%20modeling%20of%20an%20uncrewed%20surface%20vessel%20with%20experimental%20validation.pdf)

### 4.3 验证结果和对三步路线的启示

- 训练集内，custom library 的平均 RMSE 比 polynomial models 低 26.8%，标准差也更低；论文将其解释为 grey model：既保留物理先验，又允许数据发现非线性项。
- 二阶多项式在训练集表现好，但 holdout/k-fold 泛化差，表现出过拟合；只用直线训练的模型无法可靠预测圆周机动，反之亦然。机动覆盖必须按速度、半径、加减速、转向和环境分层，而不能随机打散时间行。
- 第一个直线机动出现异常误差；论文缺少物理环境传感器，推测附近船舶引起波浪扰动，但不能把推测当成已观测事实。
- 用 8 次机动训练、独立机动测试时，模型直接接收物理资产的 `u,v,r` 修正。6.25、2.5、1.22 Hz 更新较好；0.30、0.24 Hz 会出现积分误差累积。yaw rate 比平移速度更稳定，但平移状态仍需要周期性传感器校正。[本地 PDF pp. 7-11](../../paper/SINDy-based%20modeling%20of%20an%20uncrewed%20surface%20vessel%20with%20experimental%20validation.pdf)
- 论文明确提出后续应加入风向/风速、流速、RTK GPS、高频传感器，用 VRX 生成更广轨迹，并把 SINDy 用作 baseline physics model 上的 correction/residual model，再以仿真和真实海试共同验证。[本地 PDF pp. 10-12](../../paper/SINDy-based%20modeling%20of%20an%20uncrewed%20surface%20vessel%20with%20experimental%20validation.pdf)

## 5. 三篇论文的重叠、差异和不能互相替代的部分

| 能力 | 论文二：Unity DT | 论文一：DRL-NMPC sync | 论文三：SINDy Otter |
|---|---|---|---|
| 场景/地图/可视化 | Unity、Trondheim Fjord、CAD/elevation、ENC/天气概念 | ENC 与物理风浪仿真 | DT 中嵌入动力学，重点不是 3D 场景 |
| 船舶模型 | 3-DOF 非线性模型；目标船用 constant velocity | 3-DOF Telemetron；M、D、C、扰动 | 3-DOF Otter；从实船 I/O 数据稀疏发现方程 |
| RL 角色 | 路径/COLAV 名义控制 | NMPC 权重调优或 M/D 参数搜索 | 无 RL |
| 安全约束 | PSF/NMPC 修改 RL 动作 | NMPC 状态/输入/软约束，未接实船 | 无 COLAV safety filter |
| 目标跟踪 | AIS + 合成 LiDAR + KF/椭圆拟合 | COLAV 场景中的交叉目标 | 非研究重点 |
| 实船证据 | 无真实 ASV 闭环，论文明确 loop closed = no | 无实船同步，结论要求 real-world validation | 有 Otter 实船机动、留出测试和 DT 比较 |
| 主要可复用物 | 感知/融合/what-if/安全屏障接口 | 有界参数更新、solver-health reward、NMPC 执行 | 数据契约、激励设计、可解释残差、独立轨迹验证 |

因此，三篇论文应组合成不同层：SINDy/物理模型负责“船怎么动”，Unity/目标跟踪负责“看到了什么、未来可能怎样”，NMPC/PSF 负责“在约束下执行什么”，RL 只负责离线调参或提出候选动作。不能把 RL 的 reward 最优直接当成船长意图，也不能把 PSF 的安全修正当成模型同步。

## 6. 尺度、工况与 45 m FCB 的迁移边界

### 6.1 已有论文对象的尺度

| 对象 | 公开规格/论文事实 | 工况含义 |
|---|---|---|
| Otter | 2.0 m x 1.065 m x 1.08 m，62 kg，4.5 kn，30 kg payload；厂商定位 sheltered/coastal | 小型电动双体 USV；适合验证传感器、I/O 日志、辨识流程，不可直接提供 45 m FCB 的水动力系数 |
| Telemetron | 实船验证资料：8.45 m x 2.71 m，1,675 kg，34 kn；class C 限制为风 13.8 m/s、浪高 2 m | 高速小型 RBB，既有半排/滑行特性；与 45 m FCB 的推进、操纵、惯量和海况域不同 |
| Berg 等论文中的 Telemetron model | 论文表 5 的仿真 ground truth `M_RB` 对角含 3980 kg、3980 kg、19703 kg m2；没有提供几何、吃水、装载或由实船日志估计这些数值的过程 | `M_RB` 可能与 added mass/模型参数定义有关，不能直接拿来和 Telemetron 干重比较；至少不能称为已完成实船物理辨识 |
| 45 m FCB | 本项目用户给定的真实目标船；具体质量、惯量、吃水、推进器/舵、载荷和传感器延迟需以船厂/试航数据为准 | 应建立独立 full-scale model；小船数据只能用于方法、软件接口和先验范围 |

上表关于 Berg 仿真矩阵与 Telemetron 实船规格的差异是**边界审计推断**：矩阵质量可能包含 added mass 或其他建模约定，论文没有给出映射，因此不能据此断言论文数值错误；只能断言其没有提供足够证据证明该矩阵来自 45 m 或真实 Telemetron 日志。

### 6.2 对 FCB 必须重新辨识/校准的量

1. **刚体与附加质量**：质量、重心、`I_z`、附加质量矩阵，随燃油/载荷/吃水变化的版本。
2. **水动力和推进**：线性/二次/交叉阻尼，推进器推力曲线、舵效、死区、饱和、反向迟滞、执行器时间常数和分配矩阵。
3. **环境扰动**：风、流、波浪方向/谱、浅水/靠岸效应，以及不可观测扰动的估计误差和置信度。
4. **导航/感知链路**：GNSS/INS/罗经/雷达/AIS/视觉时间戳、坐标变换、延迟、丢包、噪声和协方差；论文三的 0.24-0.30 Hz 漂移警告说明低频修正不可接受地依赖模型。
5. **运行域**：低速操纵、巡航、加减速、转弯半径、不同载荷、风浪流组合、靠岸/狭水道和多船会遇。45 m FCB 不能只用 Otter/Telemetron 的平静水、单船和短时机动覆盖。

## 7. 真船数据设计：动作、意图、回放与校准必须分层

### 7.1 建议的不可变原始数据契约

每条记录保留 `event_time`、`receive_time`、`source_time`、`source`、`frame_id`、`sequence_id`、`quality`、`config_hash`；不要只保存渲染后的轨迹。至少分开保存：

| 层 | 记录内容 | 解释边界 |
|---|---|---|
| 观测 `observation` | GNSS/INS/罗经、速度、位置、目标船原始检测、AIS/radar/视觉点迹、协方差、丢包/延迟 | 传感器看到的内容，不等于真实状态 |
| 环境 `environment` | 风速/向、流速/向、波高/周期/向、海图、浅水/岸线、能见度 | 已测、外部预报、模型估计必须有 provenance 标签 |
| 命令 `command` | L2 路径/速度目标、L3 COLAV decision、L4 desired heading/speed、L5 actuator setpoint | “系统发了什么” |
| 执行 `actuation` | 实际油门/舵角/推进器反馈、饱和、故障、执行器延迟 | “船实际执行了什么” |
| 状态 `state` | 融合后的 pose/velocity、估计扰动、CPA/TCPA、风险和规则阶段 | 必须记录估计器版本与置信度 |
| 人员 `operator_action` | 船长手柄/舵/车/模式切换/接管/语音或事件标记 | observed action；不自动解释为 intent |
| 意图 `intent_hypothesis` | 目标航向、避让目的、保持/让路判断、靠泊/返航等 | 由任务计划、命令上下文或事后标注推断；保留 evidence、annotator、confidence、unknown |

船长动作与意图的判定规则：

- `observed_action` 只来自时间对齐后的手柄、舵/车命令和执行器反馈。
- `intent` 只能来自显式任务计划、口令/模式、连续命令上下文或事后人工标注；由轨迹反推的意图必须标为 hypothesis。
- 遇到紧急接管、通信延迟、执行器饱和、避浪或规避未知障碍时，不要把结果动作强行标成稳定策略；允许 `unknown/ambiguous`。
- 训练/评估算法时，分别报告“复现 observed action 的能力”和“达到安全/任务目标的能力”；两者不是同一指标。

### 7.2 两种回放不能混为一谈

| 模式 | 输入 | 状态是否被替代策略改变 | 能回答的问题 | 不能回答的问题 |
|---|---|---|---|---|
| 开放环 decision replay | 原始/校正后的历史 observation、目标、环境和时间戳；算法输出不回写到历史状态 | 否，沿用实船观测状态 | 同一观测下 L3/L2-L5 会发什么命令？与船长动作、原系统输出差多少？延迟/规则/solver 是否一致？ | 如果换策略执行，船会走哪里、是否会碰撞 |
| 闭环 counterfactual replay | 历史初始状态 + 校准后的动力学/执行器/环境模型 + 候选策略 | 是，替代动作推进 DT 状态，之后观测由模型产生 | 换策略、换参数、换风浪流后，CPA、净空、路线、能耗和接管窗口如何变化？ | 船长当时真实想法；若模型未校准，也不能宣称真实结果 |

开放环先做确定性算法和接口验收；闭环再做安全/性能反事实。开放环结果不能冒充真实船回放中的“策略效果”，闭环结果不能冒充真实船历史轨迹。

### 7.3 建议校准循环

1. **数据完整性**：固定时钟源、时间偏移、坐标系、安装杆臂、传感器质量标记；先做原始日志可重放。
2. **状态/输入重建**：用 GNSS/INS/罗经和 actuator feedback 重建 `eta, nu, r`；区分 command、received、applied、measured。
3. **激励分层**：按直航、加减速、左右转、不同速度/半径、不同载荷和海况分组；不要随机打散同一段时间序列。
4. **基线模型 + 残差模型**：先拟合可解释 3-DOF physics model，再用 SINDy/稀疏 residual 捕获未建模项；环境扰动单独估计，避免把风浪误吸收到船体阻尼。
5. **独立验证**：按航次/机动/海况留出整段 test；同时检查状态 RMSE、航迹/航向、输入饱和、solver feasibility、CPA/TCPA、最小净空和恢复/回航连续性。
6. **版本化**：模型参数、状态估计器、地图、场景、算法、ROS2 QoS、代码 commit、随机种子和数据 manifest 必须绑定；任何校准结果均生成新版本，不覆盖原始证据。
7. **影子运行再上船**：先只接收真实 observation、不发执行命令；开放环通过后做受限闭环试验，保留人工接管和硬安全边界。

## 8. 对 Colav-Simulator -> ROS2 -> 45 m FCB 的三步建议

### Step 1 - Colav-Simulator：建立可重复的算法/场景孪生

定位为 Level 0/1 到 Level 3 的可验证仿真基线：在 ENC、风浪流和 3-DOF/推进模型中运行 L3 COLAV，保存 scenario seed、观测、候选动作、最终执行动作、CPA/净空、solver status 和路线恢复。可借鉴论文一的 bounded DRL-NMPC tuning、论文二的 target-tracking/PSF 接口、论文三的 train/test 分段和残差模型；不能在此阶段宣称已经同步 45 m FCB。

验收重点：同一 trace 重放得到相同决策；Python/C++ 之后使用同一状态/输入定义；单船、多船、静态障碍、风浪流和恢复阶段都留下可比较指标。

### Step 2 - ROS2：先做时序和接口等价，再做全栈闭环

把 Colav-Simulator 作为可替换 plant/trace source，让 L2 planner、L3 COLAV、L4 guidance、L5 control 通过 ROS2 使用统一消息和 frame。先 SIL，随后在需要时 HIL；记录 message stamp、publish/receive/apply 时间、DDS QoS、队列深度、丢包、执行器饱和和每个求解器状态。开放环比较 Python reference 与 ROS2 C++ 实际输出，闭环才比较航迹和安全结果。

论文证据只能支持“模拟控制链路 + 安全过滤 + 模型更新”的分层架构，不能替代 MASS-L3 的真实 ROS2 runtime、L2/L4/L5 契约和硬件时序验收。

### Step 3 - 45 m FCB：先实船数据回放，再校准孪生，最后受限部署

建议顺序：

1. 试航全量采集并冻结原始日志；建立上述数据契约和船长 action/intent 双层标注。
2. 用开放环 replay 检查 L2-L5/L3 决策、传感器延迟、规则阶段和接管事件。
3. 用独立航次做 45 m FCB 动力学、执行器和环境扰动校准；必要时用 SINDy residual，而不是直接复用 Otter/Telemetron 系数。
4. 在校准 DT 中运行闭环 counterfactual，做风浪流、多船、靠岸和故障场景的 what-if；报告不确定性和参数版本。
5. 进入影子模式，再选择有硬安全边界、人工随时接管的短时受限闭环；每次真实部署结果回灌为新数据集，不能覆盖旧模型或把单次成功当成泛化证明。

建议把“模型同步完成”定义为可审计条件：在独立航次/工况上，状态预测、执行器响应、航迹/航向、CPA/TCPA、最小净空、恢复连续性和延迟均达到预先冻结的门限；同时开放环决策 replay 与闭环反事实 replay 分别通过。仅有论文一类仿真 reward、或论文三类单船动力学 RMSE，不足以满足此条件。

## 参考来源

### 本地论文

- `paper/Digital twin syncing for autonomous surface vessels using reinforcement learning and nonlinear model predictive control.pdf` - Berg, Menges, Tengesdal, Rasheed, *Scientific Reports* 15, 9344 (2025). 重点页：pp. 1, 3-7, 9-16, 17-18。
- `paper/DIGITAL TWIN OF AUTONOMOUS SURFACE VESSELS FOR SAFE MARITIME NAVIGATION ENABLED THROUGH PREDICTIVE MODELING AND REINFORCEMENT LEARNING.pdf` - Menges, Von Brandis, Rasheed, arXiv:2401.04032v2 / OMAE 2024. 重点页：pp. 1-9。
- `paper/SINDy-based modeling of an uncrewed surface vessel with experimental validation.pdf` - Kandemir, Coates, Hasan, *Applied Ocean Research* 165 (2025) 104825. 重点页：pp. 1-12。

### 官方/第一方来源

- [Scientific Reports: Digital twin syncing for autonomous surface vessels using reinforcement learning and nonlinear model predictive control](https://doi.org/10.1038/s41598-025-93635-9)
- [arXiv: Digital Twin of Autonomous Surface Vessels for Safe Maritime Navigation Enabled through Predictive Modeling and Reinforcement Learning](https://arxiv.org/abs/2401.04032)
- [OMAE 2024 DOI: Digital Twin of Autonomous Surface Vessels for Safe Maritime Navigation Enabled through Predictive Modeling and Reinforcement Learning](https://doi.org/10.1115/OMAE2024-122628)
- [Elsevier DOI: SINDy-based modeling of an uncrewed surface vessel with experimental validation](https://doi.org/10.1016/j.apor.2025.104825)
- [Maritime Robotics: The Otter](https://www.maritimerobotics.com/otter)
- [Kufoalor et al.: Autonomous maritime collision avoidance - field verification of autonomous surface vehicle behavior](https://doi.org/10.1002/rob.21919)
