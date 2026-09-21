# 幻灯片讲稿与来源

本稿采用本轮用户定义：L1为传感器与态势融合层。所有船舶/轨迹插图均为概念示意，非实测数据或已验收结果。

## 1 45米FCB数字孪生

项目作用 · 三步走战略 · 近期行动



算法验证；Colav-Simulator

系统集成；ROS2 · L1–L5

数据迭代；实船采集与模型校准



路线规划简报。三阶段共用场景、模型、数据与评价；不代表当前已实现或完成实船验证。L1定义依据用户本轮更正。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

## 2 数字孪生在项目中的作用

用可重复试验，利用有限的实船机会



算法试验场；批量运行风浪流与会遇场景

系统联调台；观察L1–L5协作与故障响应

海试数据实验室；反复回放、校准模型、比较策略



减少每次上船才能发现的问题；扩展海试前后的研究窗口。价值来自可重复的物理/软件/数据试验，不以画面逼真替代验证。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

## 3 L1提供共享态势

规划、避碰、导引、控制共用同一态势来源



L1 传感器与态势融合；本船状态 · 目标航迹 · 环境估计

L2 规划；L3 避碰；L4 导引；L5 控制

计划与指令；执行器与船舶；传感器反馈



用户定义优先：L1=传感器与态势感知融合。图为逻辑合同；正式实现仍需航线/控制权仲裁及接口适配。L1输出含质量/时间戳，态势不等于仿真真值。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

User clarification: L1 sensors and situational awareness fusion, shared source for other layers

## 4 数字孪生的四个组成部分

场景、船模、软件与数据共同构成验证平台



世界与环境；航道、目标船、风浪流

船舶与执行器；动力学、舵桨、时滞与饱和

传感器与显示；观测误差、L1输入、三维展示

实验与数据；场景编排、记录、评价、回放



职责可以是同进程模块，不要求拆微服务。外部Plant拥有位姿积分时，三维后端不重复计算运动。统一环境同时供载荷、感知与显示。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

## 5 三步走，共用一条验证闭环

阶段递进，采集准备并行前置



第一步：算法验证；Python实验 + 数字船 + 三维场景

第二步：系统集成；真实ROS2节点 + 仿真设备接口

第三步：数据迭代；实船记录 + 模型校准 + 回归验证

现在启动采集准备；信号清单 · 时间同步 · 记录演练



三个阶段是统一平台的运行配置，不是重做三套系统。第三步采集方案不能等第二步完成才开始。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

## 6 第一步：接入Colav-Simulator

先完成一个可重复的环境避碰闭环



输入；会遇场景 · 风浪流 · 模型参数

执行；简化L1 → 避碰算法 → GNC → 船模

显示与记录；船舶运动 · 计划轨迹 · 环境载荷

产物；场景配置 + 决策记录 + 三维回放



第一步可用目标级/理想观测L1替身，但需明确注入层级。复用现有实验/GNC/船模；三维集成不同时改避碰求解器。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

## 7 第一步验收：过程与证据

能展示，也能复现和评价



场景覆盖；对遇 · 交叉 · 追越 · 多船

完整过程；监视 → 避让 → 通过 → 恢复

复现检查；同一配置，开关显示结果一致

评价报告；本船安全 · 全船安全 · 规则行为 · 任务完成



评价依据既有场景集和预先定义容差；验收未来待执行。物理载荷开关应能解释船舶响应，不能只检查海浪动画。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

## 8 第二步：真实ROS2全栈联调

L1–L5运行目标软件，数字船替代实船设备



真实ROS2软件；L1 态势融合；L2 规划 → L3 避碰 → L4 导引 → L5 控制

仿真设备边界；传感器数据 ↔ 执行器命令与反馈

数字船与环境；FCB船模 · 舵桨模型 · 风浪流

验证目标；接口协作 · 模式切换 · 故障响应



使用生产包/commit和真实DDS执行。既有嵌入式C++核心通过不等于ROS2全栈通过。L1融合也必须作为生产节点参与此阶段。逐模块换入，替身不能计入最终全链路验收。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-ros2-twin-platform-evidence.md

## 9 第二步先冻结四类合同

把时序、语义与控制权变成可验证接口



态势合同；坐标、单位、时间戳、质量

计划合同；航线、速度、有效期、接纳反馈

执行合同；唯一控制权、命令、实际反馈

时钟与通信；步进、重置、QoS、超时处理



近期需要解决的具体缺口包括wall timer/物理wall dt、ROS2桥接、唯一积分和命令仲裁。use_sim_time本身不保证确定性；既有FMI wrapper未证明真实FMU执行。验收应包含真实节点、QoS、reset、故障和目标硬件时间行为。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-ros2-twin-platform-evidence.md

## 10 第三步：采集可校模的数据

同时记录命令、反馈、状态与当时态势



本船与环境；位置、航向、速度、IMU、风流与装载

命令与执行；舵桨指令、实际反馈、模式与接管

L1与周围交通；原始传感器、融合航迹、时间与质量

数据包；MCAP + 原始文件 + 参数版本 + 校验清单



原生频率与丢帧统计，保留设备时间和接收时间。海流/波浪未测时标注未测而非伪造真值。MCAP和原始视频/雷达旁路文件共用manifest和时钟映射。设备库存仍需团队确认。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-twin-sync-identification-evidence.md

## 11 四种回放，四种问题

分清历史事实、模型预测与策略假设



历史重现；船长当时怎样开船？

模型验证；同样舵桨输入，船模响应是否一致？

决策回放；同样观测，新算法会提出什么动作？

反事实闭环；执行新动作后，仿真结果会怎样？



反事实船位改变后，旧相机/雷达画面不能作为新位姿反馈；需重新生成观测或限定目标级近似。历史目标不响应是假设，不能宣称真实交互。seek需重置/快照与预热，不是播放器移动位置即可。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-twin-sync-identification-evidence.md

## 12 模型校准与船长行为分析

物理响应和决策意图分别建立证据



模型校准；时钟与坐标 → 执行器 → 船体 → 环境残差

船长行为；何时避让、怎样操纵、何时恢复

独立验证；按航次留出数据，检查多步预测

更新原则；通过回归后更新模型，意图依靠复盘标注



先灰箱校准，再根据残差考虑SINDy/学习方法。按独立航次切分，避免相邻采样随机打散泄漏。船长轨迹只支持行为推断，不能独自证明意图/最优性。更新离线候选，非自动更新船载控制器。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-twin-sync-identification-evidence.md

## 13 NTNU经验与平台选择

借鉴分层与验证方法，保留后端替换能力



NTNU架构；海事模型 + 三维传感器 + 自治软件

研究边界；仿真同步不等于实船验证

本项目选择；Colav编排 · ROS2集成 · 可替换三维后端

先做构建验证；Gemini已归档，ROS2适配需补齐



来源：Autoferry Gemini (2020), Hanssen game thesis (2022), milliAmpere2 design/testing (2025), Berg syncing (2025), Menges predictive/RL (2024), Kandemir SINDy (2025)。Gemini公开适配器ROS1、主仓库归档；PyGemini仅列研究候选，不承诺安装成熟度。SINDy有小型Otter数据但不直接迁移FCB参数。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-ntnu-gemini-evidence.md

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-twin-sync-identification-evidence.md

https://github.com/Gemini-team/Gemini

https://github.com/Gemini-team/ros_adapter

https://doi.org/10.1038/s41598-025-93635-9

https://doi.org/10.1016/j.apor.2025.104825

https://doi.org/10.1088/1757-899X/929/1/012032

https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3028969

https://doi.org/10.1115/1.4067370

https://doi.org/10.1038/s41598-025-93635-9

https://arxiv.org/abs/2401.04032

https://doi.org/10.1016/j.apor.2025.104825

## 14 近期可立即启动的四项工作

先明确接口与数据，再完成最小联调



统一L1–L5接口；各层负责人：字段、单位、频率与控制权

核对FCB参数；船模负责人：参数来源、缺口与适用范围

验证三维连接；仿真负责人：外部位姿、时钟与重置

演练海试记录；采集团队：信号清单、同步与离线回放



角色为建议分工，非已获团队承诺。每项产物：接口字典v1；参数台账；构建/外部位姿驱动记录；可离线回放的数据演练包。现在就可启动，先确认同事包版本和设备数据可获得性。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-ros2-twin-platform-evidence.md

## 15 首个可验收切片

一艘FCB、两艘目标、一组风浪流



范围；既有避碰算法 + 简化L1 + 数字船

演示；三维同步显示避让与恢复航线

检查；开关显示结果一致，记录可回放

下一步；接真实ROS2节点，持续准备实船采集



这是建议的首个实施切片，结果待实际运行；三维只订阅已计算状态。配置/模型哈希、trace、载荷、评价与回放为交付证据。执行范围先冻结，之后推进ROS2全栈及真实数据校准。



图像为概念示意，不代表实测船型、轨迹或已完成验收。

L1=传感器与态势融合；L2=规划；L3=避碰；L4=导引；L5=控制。



来源：

/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md
