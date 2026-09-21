# NTNU Gemini / OSP / milliAmpere 证据整理

研究日期：2026-09-17。本文只记录已在本地 PDF 或一手网页中核实的事实；“可迁移到 45 m FCB”的内容单独标为工程推论。

## 先给结论

NTNU 的公开材料支持一条清晰的分层架构：

```text
OSP/FMI：海事动力学、环境、执行器等传统模型的协同仿真
        |
        +-- Gemini/Unity：3D 场景、视觉/红外/雷达/激光雷达传感器渲染
        |
ROS：感知、目标跟踪、态势理解、规划、避碰以及可复用的自治软件
        |
真实船：DP/推进/传感器/通信；必要时接入供应商专有控制平台
```

这不是“Gemini 已经是一个可直接接入 ROS2 的完整数字孪生产品”的证据。最直接的 NTNU 架构材料明确说，传统海事模型在 OSP/FMI，Unity/Gemini 负责虚拟世界和外感知传感器，自治软件在 ROS 中运行，并支持使用自治软件精确副本的 SiL；但该材料是 milliAmpere II 仿真/验证方案论文，不是公开可复现的完整发布包。[Torben et al., *Towards Contract-based Verification for Autonomous Vessels*, 文内 pp.17-19（下载 PDF 页 117-119）](https://assor.folk.ntnu.no/PhD%20Thesis/PhD_Thesis_Torben.pdf)

对当前工程选择最关键的事实是：官方 Gemini 仓库已于 2025-11-12 归档、只读；根仓库是 MIT License、没有发布版本，README 仍说明它只是 Unity 项目，没有单一可执行文件。[Gemini 仓库](https://github.com/Gemini-team/Gemini)；[README](https://github.com/Gemini-team/Gemini/blob/master/README.md)；[LICENSE](https://github.com/Gemini-team/Gemini/blob/master/LICENSE)。公开的 `ros_adapter` 是 ROS1/catkin 适配器，使用 `catkin_make`、`roslaunch`、`rospy`，Docker 基于 `ros:melodic-ros-base`；没有 ROS2/ament/rclcpp 证据。[ros_adapter README](https://github.com/Gemini-team/ros_adapter/blob/master/README.md)；[package.xml](https://github.com/Gemini-team/ros_adapter/blob/master/package.xml)；[Dockerfile](https://github.com/Gemini-team/ros_adapter/blob/master/docker/Dockerfile)

因此，Gemini 可以作为“可借鉴的 Unity 传感器/可视化层”和历史接口参考；接入当前 ROS2 MASS-L3 需要自建 ROS2 bridge 或重新实现适配层，并把 45 m FCB 的动力学、传感器、时钟、延迟和通信模型重新标定。

## 1. NTNU 架构证据：OSP/FMI + Gemini/Unity + ROS

### 1.1 最完整的公开架构图

Torben 等人的 milliAmpere II 仿真章节给出最完整的公开架构描述：

- 模拟器由 NTNU、Zeabuz 和 DNV 在 TRUSST 项目中共同开发；
- 传统海事仿真模型部署在 OSP，OSP 是基于 FMI 的海事协同仿真标准/平台；
- 3D 虚拟世界和外感知传感器模型部署在 Gemini，Gemini 基于 Unity；
- 自治软件运行在 ROS，并支持使用自治软件“精确副本”的 SiL；
- COTS motion-control system 也可进入 SiL，但运行在供应商专有平台；
- Figure 9 将系统划为 `Operative environment`、`Autonomy system`、`Plant`：环境侧含可视化/虚拟世界、交通、风浪流和静态场景；自治侧含感知传感器、目标检测、融合/理解、导航决策、COLAV、自动靠泊和路径规划；Plant 侧含导航传感器、船舶动力学/运动学/环境载荷、执行器、推进控制和 DP/推力分配。[预印本 pp.17-19（下载 PDF 页 117-119，Figure 9-10）](https://assor.folk.ntnu.no/PhD%20Thesis/PhD_Thesis_Torben.pdf)

这张图可以直接作为三阶段架构的参考分区，但不能把论文中的架构图当成当前仓库已经具备的产品能力。论文同时强调：组件级验证可以删减或简化其他模块；完整环境用于顶层集成测试，轻量环境用于提高覆盖率。[同上，文内 p.18（下载 PDF 页 118）](https://assor.folk.ntnu.no/PhD%20Thesis/PhD_Thesis_Torben.pdf)

### 1.2 OSP 的标准边界

当前 OSP 官方文档说明：OSP 以 FMI 协同仿真接口连接模型，支持 FMI 1.0 和 FMI 2.0；系统结构可以用 SSP 或 OSP System Structure 描述，OSP-IS 为变量组连接增加语义、单位转换和配置预验证。核心软件包括 C++ `libcosim`、C wrapper、命令行工具、Java wrapper、验证器和配置工具。[OSP 官方软件说明](https://open-simulation-platform.github.io/)

当前 `libcosim` 文档说明它是固定步长 master，可配置基础步长，支持模型独立步长、变量变换、结果记录和分布式协同仿真；另有 `libcosimpy` Python wrapper，可从 OSP 或 SSP 配置创建执行。[libcosim 文档](https://open-simulation-platform.github.io/libcosim)；[libcosimpy README](https://github.com/open-simulation-platform/libcosimpy)

### 1.3 当前 OSP 的 milliAmpere demonstrator

OSP 官方当前的 milliAmpere 页面描述了一个 FMI 2.0 demonstrator：把原船软件中不依赖 rospy 的控制/Plant 核心重新包成八个 FMU，包括 WP manager、ALOS guidance、reference filter、navigation、DP controller、thrust allocation、vessel plant 和 wind。所有信号使用 NED 和 SI 单位。模型/FMU 未在页面公开，访问需要 milliAmpere 仓库权限。[OSP milliAmpere reference model](https://open-simulation-platform.github.io/cosim-demo-app/milliAmpere)

这证明 OSP 目前有可用于控制/动力学协同仿真的 milliAmpere 参考路线，但页面没有声称它与 Unity/Gemini 或 ROS2 已完成互联；它不能替代对当前 MASS-L3 ROS2 栈的适配和验证。

## 2. Gemini 当前状态与 ROS 兼容性

### 2.1 当前仓库状态

2026-09-17 现场核对官方 GitHub：

- `Gemini-team/Gemini` 页面显示 **archived by owner on Nov 12, 2025**，仓库只读；
- 根仓库显示 MIT license、没有 Releases；LICENSE 明确允许复制、修改、发布、再许可和销售，但要求保留版权及许可声明；
- README 说明 Gemini 是 Unity visual simulator，通过 API 与虚拟船舶/环境交互；当前没有 Unity 单一 executable，只提供 Unity project；
- 当前 master 的最新提交可由仓库历史核对到 2021-09-30（commit `ce538dff7e1a8d1f1a249d7eeed2f5349fdf1b33`）；这不是活跃维护状态的推测，而是已抓取仓库的 git 历史事实。

来源：[仓库状态与目录](https://github.com/Gemini-team/Gemini)；[README 原文](https://raw.githubusercontent.com/Gemini-team/Gemini/master/README.md)；[MIT LICENSE 原文](https://raw.githubusercontent.com/Gemini-team/Gemini/master/LICENSE)；[仓库提交历史](https://github.com/Gemini-team/Gemini/commits/master)

仓库 `simulation.proto` 的 package 名称是 `GeminiOSPInterface`，定义 `DoStep` 和 `SetStartTime`，消息只有船舶 N/E/heading、time、stepSize 等字段。[simulation.proto](https://github.com/Gemini-team/Gemini/blob/master/API/Protobuf/ProtoFiles/simulation/simulation.proto) 但当前 Unity `SimulationServiceImpl` 的实现只是把请求中的 pose 写入 Unity 船舶 transform、更新传感器时间并返回 success；`stepSize` 在实现中没有参与推进，`SetStartTime` 也没有实际设置仿真时钟。[SimulationServiceImpl.cs](https://github.com/Gemini-team/Gemini/blob/master/Gemini-Unity/Packages/gemini/Runtime/Gemini/Scripts/Networking/Services/Simulation/SimulationServiceImpl.cs) 因此 `GeminiOSPInterface` 这个命名不能单独证明已实现 FMI/OSP master 或完整 OSP 联调。

### 2.2 ROS 适配器是 ROS1

官方 `ros_adapter` README 要求在 `gemini_ws` 中执行 `catkin_make`、source `devel/setup.bash`，再用 `roslaunch` 启动 server；`package.xml` 使用 `catkin`、`rospy`、`std_msgs`；Dockerfile 基于 `ros:melodic-ros-base`。适配器通过 gRPC 接收 Gemini 数据，再发布 ROS 图像、PointCloud2、雷达 spoke、clock、pose、twist 和 TF。[README](https://raw.githubusercontent.com/Gemini-team/ros_adapter/master/README.md)；[package.xml](https://raw.githubusercontent.com/Gemini-team/ros_adapter/master/package.xml)；[server.py](https://github.com/Gemini-team/ros_adapter/blob/master/scripts/server.py)

该仓库没有 ROS2 `ament_cmake`、`rclcpp`、`rclpy`、ROS2 message package 或 `ros2 launch` 证据。结论应写成“现成适配器可复用消息语义和 gRPC 思路，但当前公开实现是 ROS1；ROS2 需新增适配层”，不能写成“Gemini 已兼容 ROS2”。

## 3. 三篇本地 NTNU PDF 的实验边界

### 3.1 *Autoferry Gemini: a real-time simulation platform...* (2020)

本地文件：[Autoferry Gemini PDF](<../../paper/Autoferry Gemini- a real-time simulation platform for electromagnetic radiation sensors on autonomous ships.pdf>)。

- Figure 1（印刷 p.3，PDF p.4）展示 Unity HDRP/G-buffer 同一场景状态下的 VL/IR pipeline，以及通过 custom depth pass、compute shader 生成 lidar/radar；论文的贡献是 GPU 上并发传感器仿真，不是自治系统闭环。[pp.2-4](<../../paper/Autoferry Gemini- a real-time simulation platform for electromagnetic radiation sensors on autonomous ships.pdf>)
- 在一台 GTX 1050 笔记本上，表 3 给出单传感器约 45 Hz VL、80 Hz IR、50 Hz lidar、35 Hz radar，多传感器同时运行 15 Hz（印刷 p.10，PDF p.11）。
- 评价明确是 qualitative evaluation；“传感器输出如何转移到真实世界”超出论文范围（印刷 p.7，PDF p.8）。IR 使用艺术化 emissivity texture；雷达结果与真实数据相似度有限，主要缺少 RCS；lidar 存在 beam-shape accuracy/performance trade-off；多传感器实验发现同步误差但未修复（印刷 pp.8-10，PDF pp.9-11）。
- Figure 3-6 是模拟图与 milliAmpere 实测 VL/IR/lidar/radar 的定性并排比较，不是传感器级定量标定，也没有证明 ROS、OSP、COLAV 或控制器已闭环运行。

可迁移的是“统一场景时钟 + 传感器并发生成 + API/bridge”；不可直接迁移的是传感器真实性、雷达 RCS、材料/海况模型和 45 m 船舶的动力学闭环。

### 3.2 *Developing a video game for research and prototyping...* (2022)

本地文件：[Game thesis PDF](<../../paper/Developing a video game for research and prototyping of unmanned maritime vessels.pdf>)。

- MVP 明确“不是准确模拟传感器和自治系统”，自治航行由预定义 Bézier path 驱动，运动用 Unity PhysX；碰撞避免只是“前方有船则停止”（印刷 pp.8-9，PDF pp.15-16）。
- Crest 提供三维动态波、浮力和阻力，改善环境/操作体验，但它仍是 Unity 外部资源，不等于经过实船标定的风浪流和船舶动力学（印刷 p.15，PDF p.22）。
- 数据记录包括船位、速度、艏向、输入、自治/手动状态、到码头距离、靠泊状态、碰撞日志和 Unix timestamp；V3 还支持一般船舶轨迹回放、详细 CSV 和最多八艘 ferry 的监控（印刷 pp.13、23-24，PDF pp.20-21、30-31）。这对第三步“真船数据回放/对齐”有直接设计启发。
- 实际研究是远程操作/HMI：Case 2 招募 16 名有 gamer 背景的参与者，两个脚本场景分别是 autopilot 故障后手动靠泊、两艘船碰撞风险下手动接管；测试在 Shore Control Lab 操作台完成，Case 1 的初步用户测试因排期远程完成（印刷 pp.25-27，PDF pp.32-34）。
- 论文结论说该方法适合早期远程操作原型；“详细自治系统”仍应进一步探索 Gemini 集成（印刷 pp.36-38，PDF pp.43-46）。所以这项 ROC/HMI 研究不能当成完整 Plant + COLAV + ROS/OSP 的闭环验收。

### 3.3 *The Autonomous Urban Passenger Ferry milliAmpere2: Design and Testing* (2025)

本地文件：[milliAmpere2 PDF](<../../paper/The Autonomous Urban Passenger Ferry milliAmpere2- Design and Testing.pdf>)。

- 真实船是 8.65 m、3.5 m beam、6 t、四个 10 kW azimuth pods、最多 12 人；2022 年进行了三周 public trial，船上始终有 safety operator（印刷 pp.2-3，PDF pp.2-3）。
- Figure 6/7（印刷 pp.5-6，PDF pp.5-6）给出实船架构：多种 RGB/IR camera、两个 lidar、X-band radar、GNSS/IMU、SITAW、COLAV、DP、通信和四个 azimuth thrusters。自主模式由 autonomy computer 生成 waypoint/trajectory 给 DP；态势数据不足时进入 minimum-risk station keeping（印刷 pp.5-6，PDF pp.5-6）。
- 2022 ROC 人因实验使用 milliAmpere2 的 Gemini digital twin，重建实际 crossing 场景；界面含 PTZ cameras，研究远程操作员的 safety-critical intervention。论文报告操作员最多同时监控三艘 virtual ferry（印刷 pp.6-7，PDF pp.6-7）。这是 ROC/人因验证的数字孪生用途，论文没有给出完整 Plant 参数、传感器误差闭环或等价于实船自治验收的证据。
- 真实 public trial 仍需船上 safety operator，原因是挪威海事主管机关指南和当前技术/法规约束；论文明确写道 milliAmpere2 不能脱离 safety operator 运行（印刷 p.8，PDF p.8）。三周试航约 25 次人工干预；系统整体能跟踪目标并避免潜在碰撞，但 wake/漂叶造成 false tracks 的边界案例需工程师处理和软件更新（印刷 p.8，PDF p.8）。
- 后续路线是先把 safety operator 移到有视线的 local operating center，再逐步走向 ROC；该文把它写成 future work/transition plan，不是已经完成的远程无人在船运营认证（印刷 p.8，PDF p.8）。

### 3.4 交叉核对：相机 COLAV 的真实闭环验证

Helgesen 等人的开放论文是很好的“真实船边界”对照：[MIC article](https://www.mic-journal.no/ABS/MIC-2023-2-2.asp)；[PDF](https://www.mic-journal.no/PDF/2023/MIC-2023-2-2.pdf)。

- 使用 milliAmpere2 做了单目标、纯相机态势感知的 real-world closed-loop COLAV；实验在 Trondheim 于 2022-12 完成，共六次 Canal crossings，每次目标轨迹都设计为不采取行动就会碰撞（PDF pp.55-63，尤其 p.62）。
- 目标船是 6.05 m × 2.2 m Buster XL；天气、低光和降雪都具有挑战性（PDF pp.62-63）。结果显示六次 crossing 中系统进行停车/避碰并恢复航行，但这是单目标、特定狭窄运河、纯相机方案，不是多船、多传感器、45 m FCB 或 OSP/Gemini/ROS2 全栈证明。
- 八台以 5 Hz 工作的 Ethernet cameras 造成带宽问题，实验中约 40% 图像丢失，导致早期 track death；论文把完整相机功能、更高安装高度、改进目标预测、雷达/激光雷达融合列为后续工作（PDF pp.65-66）。因此“真实闭环成功”与“系统已达到泛化/运营级可靠性”必须分开表述。

## 4. 对 45 m FCB 三阶段的可用边界

### 可直接借鉴的结构

1. **环境/船舶模型层**：参考 OSP/FMI/SSP，把 45 m FCB 的 6-DOF/受限工况动力学、风浪流、推进器/舵机、传感器时延、通信和故障模型作为可替换模型；用固定仿真时钟和统一 NED/SI 接口。
2. **感知/可视化层**：参考 Gemini 的 Unity + GPU sensor pipeline，只把它作为可视化与传感器数据生成器；通过 ROS2 bridge 发布与真船一致的 topic/message/TF，保留时间戳、frame、噪声和丢包模型。
3. **自治软件层**：在 Stage 2 接入真实的 L2-L5/L3 ROS2 节点和实际参数，记录每层输入/输出/决策/控制量；不能用 Unity 内的 scripted autopilot 代替真实节点。
4. **真船回放/校准层**：参考游戏 thesis 的 timestamped CSV/replay，以及 milliAmpere 的 false-track/人工干预记录，把真船原始传感器、导航、环境、控制、人工操作、系统模式和告警作为不可变原始记录，再生成可重放场景和参数校准集。

### 必须重新验证的内容

- 45 m FCB 与 milliAmpere2 的尺度、质量、吃水、惯量、风面积、推进/舵效、传感器高度/视场、通信链路和操作域完全不同；NTNU 小船结果不能作为 FCB 的安全阈值或动力学参数。
- Gemini 2020 论文未完成真实传感器定量迁移；其雷达 RCS、IR 材料、场景细节、同步误差和 lidar 精度边界必须在 FCB 传感器数据上重新评估。
- OSP 当前 milliAmpere demonstrator 是 FMU 协同仿真，模型访问受限；它不是 ROS2 bridge，也不是 Gemini Unity 场景。需先做接口/时钟/单位/延迟契约，再做闭环验收。
- ROC 的脚本/数字孪生研究验证了人工接管和人因问题，不等于自治全流程或无安全员运营许可；实际试航中仍有人工干预和 false-track 边界案例。

## 5. 面向项目评审的最小证据门槛

把 Stage 1-3 的“完成”分别定义为：

- **Stage 1 / Colav-Simulator**：风浪流、船舶运动、COLAV 结果和可视化能由同一仿真时钟重放；没有 Gemini/Unity 也能先完成算法级基线；接入 Unity 时能证明传感器 topic、时间戳、坐标系和延迟映射。
- **Stage 2 / ROS2 全栈**：同一 ROS2 可执行节点在仿真和 HIL/实船接口运行；L2-L5 与 L3 的实际消息、控制周期、失联/降级/安全状态和日志可审计；不能用 scripted path、special case 或 forced PASS 代替。
- **Stage 3 / 真船数据闭环**：原始数据保留、时钟对齐可复现、关键传感器/导航/控制轨迹可回放；参数校准后在独立留出数据集上验证，且报告模型预测与实船误差、人工干预和失败边界。Stage 3 的回放成功不自动等于海上运营认证。

## 一手来源索引

- [NTNU/Zeabuz/DNV, *Towards Contract-based Verification for Autonomous Vessels*](https://assor.folk.ntnu.no/PhD%20Thesis/PhD_Thesis_Torben.pdf), 尤其文内 pp.17-19 的 OSP/Gemini/ROS 架构和 Figure 9-10。
- [Vasstein et al., *Autoferry Gemini*](https://doi.org/10.1088/1757-899X/929/1/012032)，本地 PDF 页码见 §3.1。
- [Hanssen, *Developing a video game...*](<../../paper/Developing a video game for research and prototyping of unmanned maritime vessels.pdf>)；本地 NTNU thesis PDF 页码见 §3.2。论文参考的官方 Gemini 项目链接为 [Gemini-team/Gemini](https://github.com/Gemini-team/Gemini)。
- [Eide et al., *The Autonomous Urban Passenger Ferry milliAmpere2: Design and Testing*](https://doi.org/10.1115/1.4067370)，本地 PDF 页码见 §3.3。
- [Helgesen et al., *Experimental validation of camera-based maritime collision avoidance*](https://doi.org/10.4173/mic.2023.2.2)，开放 PDF 页码见 §3.4。
- [Open Simulation Platform official software](https://open-simulation-platform.github.io/)、[OSP-IS specification](https://opensimulationplatform.com/specification/)、[current milliAmpere demonstrator](https://open-simulation-platform.github.io/cosim-demo-app/milliAmpere)。
- [Gemini official repository](https://github.com/Gemini-team/Gemini)、[Gemini API simulation proto](https://github.com/Gemini-team/Gemini/blob/master/API/Protobuf/ProtoFiles/simulation/simulation.proto)、[Gemini simulation service](https://github.com/Gemini-team/Gemini/blob/master/Gemini-Unity/Packages/gemini/Runtime/Gemini/Scripts/Networking/Services/Simulation/SimulationServiceImpl.cs)、[ROS1 adapter](https://github.com/Gemini-team/ros_adapter)。
