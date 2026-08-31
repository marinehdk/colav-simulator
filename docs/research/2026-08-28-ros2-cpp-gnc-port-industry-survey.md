# ROS 2 C++ 船舶 GNC 模块移植与集成调研

日期：2026-08-28
范围：将同事的 ROS 2 Humble/C++ 船舶 4DOF 水动力（风、浪、流、执行器、RK4）、PID/SMC/NDO 控制和 ILOS 导引接入本项目。
方法：只使用 ROS 2/FMI/pybind11 官方资料、官方开源仓库/源码和原始论文；未使用 NotebookLM。本文是集成决策输入，不替项目裁决架构。

## 结论摘要

四种可行路径都能支持调试，但它们解决的问题不同：

| 路径 | 适合目标 | 主要代价/失效面 | 当前建议定位 |
|---|---|---|---|
| 纯 Python 转写 | 让 `Ship` 直接拥有可读、可单步、可覆盖的本地模块 | 方程、符号、饱和顺序、状态机和积分器发生语义漂移 | 参考实现/回归 oracle；是否作为生产模型待验证 |
| C++ 纯算法库 + pybind11 | 保留 C++ 数值实现，在 Python 仿真循环中同步调用 | ABI/生命周期/GIL/数组布局/异常/构建矩阵 | 最短的进程内闭环候选 |
| ROS 2 独立进程桥 | 保留完整 ROS2 节点、参数、日志、工具和未来实船接口 | 异步队列、QoS、时间戳、延迟、丢包、启动和进程故障 | 系统级联调候选；不应作为第一条数值等价路径 |
| FMI/FMU 封装 | 将模型作为标准化黑盒交给多工具联合仿真 | FMU 导出、通信步长、状态可见性、求解器所有权和工具兼容性 | 跨工具/供应商交付候选；不应先于接口冻结 |

这不是“选一个永远固定”的决定。可先以同一个规范化输入输出契约同时做 C++/pybind11 适配和 Python oracle，再用 ROS2/FMI 作为外部联调边界。最终选择取决于同事代码能否抽出无 ROS 依赖的算法核心、期望调试的是方程内部状态还是系统级通信行为、以及许可证和部署平台要求。

## 本项目当前边界

本地代码已经提供可替换子系统，但当前闭环仍围绕典型 3DOF surface-vessel 契约：

- `IModel.dynamics(xs, u, w) -> xdot` 和 `bounds() -> (lbu, ubu, lbx, ubx)`：`colav_simulator/core/models.py:342-369`。
- `IController.compute_inputs(refs, xs, dt) -> u`，参考为 `9 x 1` `[x,y,psi,u,v,r,ax,ay,rdot]`，控制输入为 `3 x 1`：`colav_simulator/core/controllers.py:171-193`。
- `IGuidance.compute_references(waypoints, speed_plan, times, xs, dt) -> 9 x N`：`colav_simulator/core/guidances.py:81-111`。
- `Ship` 构造函数可直接注入 `model/controller/guidance`，并在注入 guidance 时清空 COLAV：`colav_simulator/core/ship.py:470-535`。这适合先做对象级适配；YAML/Builder/schema 仍需另行接线。
- `Ship.forward` 通过本地 `erk4_integration_step` 推进；该积分器对同一个 `f(x,u,w)` 调用四次并在末端施加状态饱和：`colav_simulator/core/integrators.py:17-39`。`Simulator.step` 先 plan、后 forward，并将同一扰动结构传给模型：`colav_simulator/simulator.py:373-432`。

因此，4DOF 不是只换一个类名的问题。必须先回答：第四个自由度是什么（roll/heave/其他）、状态是否包含姿态和执行器/观测器状态、输入是广义力 `[X,Y,N,(K/Z/...)]` 还是舵角/转速、以及模型是否返回导数。若保留本项目现有 6/3/9 形状，可能需要内部 4DOF 状态加一个明确的降阶/观测投影；若要真正闭合 4DOF，则需要扩展 model/controller/guidance/integrator、轨迹记录、边界和测试契约。不能在看到 ROS 消息名后直接假定映射正确。

## 四种架构的事实与设计决策

### 1. 纯 Python 转写

**事实基础。** 官方 [PythonVehicleSimulator README](https://github.com/cybergalactic/PythonVehicleSimulator/blob/master/README.md) 将车辆建模为 Python 对象，并将 guidance、navigation、control 放在车辆/库中；其 [control.py](https://github.com/cybergalactic/PythonVehicleSimulator/blob/master/src/python_vehicle_simulator/lib/control.py) 同时展示了 pole-placement PID 和带边界层的 integral SMC；其 [actuator.py](https://github.com/cybergalactic/PythonVehicleSimulator/blob/master/src/python_vehicle_simulator/lib/actuator.py) 展示舵面/推进器动态、幅值限制和力矩映射。官方 [MSS Quick Reference](https://github.com/cybergalactic/MSS/blob/master/MSS%20Quick%20Reference.md) 列出了 3DOF/6DOF vessel、风/波/流、`rk4`、`ALOS`、`ILOS`/路径跟踪相关示例。这些仓库适合做公式和测试夹具参考，不等于同事 4DOF 模型的数值等价证明。

**必须冻结的决策。**

1. 以 C++ 快照为 oracle：固定参数、初始状态、输入、扰动、`dt`、坐标系和每一步的所有内部状态；只比较最终位姿会漏掉早期符号/饱和差异。
2. 明确积分器所有权。当前 simulator 已经做 RK4；若转写代码内部仍做 RK4，必须改成“纯导数模式”或让外层不再积分，否则是 double integration。
3. 明确每个 RK4 stage 读取的是同一个风浪流样本，还是按 stage 时间插值；有色噪声/波相位/观测器状态不能在 stage 中隐式推进四次。
4. 保留控制器、NDO、ILOS 的内部离散状态和 `reset()` 语义；每 episode、暂停/继续、重新初始化的行为都必须可测试。
5. 将参数单位、符号、饱和、抗积分饱和、舵角速率限制、死区、推力分配和异常输入处理写成契约，而不是凭 Python 命名猜测。

**优势。** 最容易在 pytest 中逐项检查、断点和记录全部内部量，且直接服从现有 `IModel/IController/IGuidance`。
**主要失效。** “按公式重写”常会改变矩阵乘法顺序、角度 wrap、浮点类型、初始化次序、离散化和饱和顺序；复杂 NDO/SMC 的切换函数或 ILOS 积分器还可能因 `dt=0`、低速、路径段切换、反向航行而漂移。纯 Python 的可读性不构成论文复现或安全闭环证据。

### 2. C++ 纯算法库 + pybind11

**事实基础。** [pybind11 CMake 文档](https://pybind11.readthedocs.io/en/stable/cmake/index.html)支持通过 `find_package(pybind11 CONFIG)` 导入；[编译文档](https://pybind11.readthedocs.io/en/stable/compiling.html)提供 `pybind11_add_module` 生成 Python 扩展。官方 [NumPy/Buffer 文档](https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html)说明 `py::array_t<T>` 的类型/维度转换，并明确数组可能具有任意 stride；[STL 文档](https://pybind11.readthedocs.io/en/latest/advanced/cast/stl.html)说明 `std::vector/map` 与 Python 容器的隐式转换通常会复制。官方 [GIL 文档](https://pybind11.readthedocs.io/en/stable/advanced/misc.html)说明 pybind11 不会自动释放 GIL，长时间纯 C++ 计算可显式使用 `gil_scoped_release` 或 [call_guard](https://pybind11.readthedocs.io/en/stable/advanced/functions.html#call-guard)；[异常文档](https://pybind11.readthedocs.io/en/stable/advanced/exceptions.html)说明 C++ 标准异常会映射为 Python 异常。

**推荐的边界形状（待同事代码确认）。** 不把 `rclcpp::Node`、ROS message、executor 或参数服务器链接进扩展；提取一个无 ROS 的 C++ core，暴露单个带版本的调用边界，例如：

```text
configure(model_params, control_params, guidance_params)
reset(initial_state, initial_internal_state, seed)
step(t, dt, state, command/reference, environment) -> {state_dot or next_state, actuator_state, diagnostics}
```

Python adapter 再把本项目的 `xs/u/w/refs` 映射到这个边界。若 `step` 返回 `next_state`，外层必须关闭该模块的内部推进；若返回 `state_dot`，必须让 C++ core 保持无副作用，尤其不能在 RK4 的四次评估中重复推进 observer/ILOS/actuator 状态。数组应在边界做 contiguous、dtype、shape 和 finite 检查；输出诊断和错误码也应是稳定的值对象，而非暴露 C++ 容器所有权。

**必须冻结的决策。**

- 支持矩阵：Python 版本、编译器、libstdc++/libc++ ABI、ROS2 Humble 的 Ubuntu 版本、x86_64/ARM；把 pybind11 扩展作为独立构建/安装目标。
- 内存/所有权：输入只读还是可写、返回数组是否拷贝、C++ 对象由 Python 还是 C++ 持有；不要把短生命周期的 C++ buffer 返回成悬空 `memoryview`。[NumPy 文档](https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html)特别提醒非 Python 管理 buffer 的生命周期责任。
- 并发：C++ core 是否线程安全、是否允许释放 GIL、是否有 Python callback；释放 GIL 后不得访问 Python 对象，且所有 observer/控制器实例都应是 per-ship/per-episode 状态。
- 异常：数值失败、非法维度、参数缺失、饱和和超时必须区分；不能在 Python adapter 中吞掉异常并静默降级到另一算法。

**优势。** 保留 C++ 数值实现和内部状态，可在同一 Python simulation time 下无 DDS 网络延迟调用。
**主要失效。** ABI 或 wheel 不匹配、数组 stride 被误当 contiguous、C++ 对象析构/线程跨越 Python 生命周期、GIL 死锁、STL 隐式复制、C++ exception 变成未分类 `RuntimeError`，以及“扩展能 import”但尚未证明方程和外层 RK4 语义一致。

### 3. ROS 2 独立进程桥

**事实基础。** ROS2 官方 [C++ publisher/subscriber 教程](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Cpp-Publisher-And-Subscriber.html)将 node 描述为通过 topic 通信的 executable process，并要求在 `package.xml`/`CMakeLists.txt` 声明依赖；[参数文档](https://docs.ros.org/en/humble/Concepts/Basic/About-Parameters.html)说明参数附属于 node、可启动时和运行时设置；[QoS 文档](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html)说明可靠性、history、depth 等策略组合，且不兼容 profile 会阻止消息传递；[ROS2 intra-process demo](https://docs.ros.org/en/humble/Tutorials/Demos/Intra-Process-Communication.html)说明可组合 node 以降低通信开销。ROS2 官方 [pluginlib 教程](https://docs.ros.org/en/rolling/Tutorials/Beginner-Client-Libraries/Pluginlib.html)说明可从共享库动态加载导出的 C++ 类；这可作为 ROS 侧插件化参考，但不自动解决 Python simulator 的接口问题。

**桥接契约要先于 topic 名。** 至少定义：

- `sim_time`、时间戳来源、固定/可变 `dt`、暂停/重置/episode id；不得让 wall-clock ROS timer 代替仿真时间。
- 状态消息（pose、body velocity、角速度、估计量）、environment（风浪流及其 frame/单位/随机种子）、guidance reference、actuator command/actual、diagnostics/error code；每条消息注明 NED/ENU、body/world、真速度/相对水速。
- 控制周期和队列深度；输入是否必须逐步一一对应，过期 command 如何拒绝，乱序/重复消息如何处理。
- QoS profile、deadline、reliability、transient/local 语义及启动顺序。可用 [ROS2 rosbag2 官方仓库](https://github.com/ros2/rosbag2)录制/回放，但 replay 仍需保存版本、参数和时间策略。

**优势。** 能保留同事的 ROS2 节点、参数、日志、launch、诊断和未来实船/硬件接口；可以单独杀掉/重启模块观察系统故障边界。ROS2 官方的节点、参数、QoS 和组合能力为此提供平台机制。
**主要失效。** DDS queue 产生的旧状态、QoS 不匹配导致的“无消息”、异步 bridge 延迟使控制器使用非同一时刻的 state/reference、ROS timer 与 simulator `dt` 漂移、启动时未初始化参数、进程崩溃后 simulator 仍继续推进、服务/话题重置不幂等。因而它更适合系统集成证据，不适合作为第一步判定数值等价。

### 4. FMI/FMU 封装

**事实基础。** [FMI 官方网站](https://fmi-standard.org/)定义 FMU 为包含 XML、binary 和 C code 的 ZIP 容器；[FMI 3.0 规范](https://fmi-standard.org/docs/3.0/)区分 Model Exchange (ME)、Co-Simulation (CS) 和 Scheduled Execution (SE)：ME 将 ODE 暴露给 importer 的求解器，CS 由 FMU 自带内部求解并通过通信点交换，SE 暴露可由 importer 调度的 model partitions。规范明确指出 CS 的 co-simulation algorithm 不属于 FMI 标准，并且 CS 通信点之间的信息传递会引入采样/延迟语义；ME 的 solver、步进和事件处理由 importer 负责。官方 [Modelica Association FMI repository](https://github.com/modelica/fmi-standard)提供规范源码、C headers 和 XML schema；官方 [Reference-FMUs](https://github.com/modelica/Reference-FMUs)用于开发、测试和调试。

**对本项目的直接含义。**

- 若 Colav-Simulator 继续拥有唯一 RK4 求解器，4DOF 水动力更接近 ME 语义：FMU 暴露 derivatives、states、parameters，importer 负责积分。但要把 ROS2 C++ 模型整理成 FMI ME FMU，并公开所有必要连续/离散状态和事件。
- 若同事代码必须保留内部 RK4、执行器、wave phase、NDO/ILOS 采样状态，CS 更接近现状；但每个 `fmi3DoStep` 只能在通信点交换，需显式记录通信步长和延迟，不能把 CS FMU 当作本地 derivative 函数。
- SE 只有在确实要让外部 scheduler 分开调度 model partitions 时才有价值；对单一 Python 仿真循环会增加调度复杂度，不能自动解决算法边界。

**优势。** 标准化动态模型交付、跨工具/团队边界清晰、可保留二进制实现并与其他 FMI 工具联合仿真。
**主要失效。** FMU 只在某平台 binary 可用、导出器与 importer 对 FMI 版本/能力 flag 不兼容、ME/CS 选错导致 double integration 或隐藏状态、CS communication step 太大导致闭环延迟、无法读出 NDO/ILOS 内部量而不利于调试、FMU reset/terminate 生命周期未对齐 episode。FMI 本身也不规定 co-simulation master algorithm，因此“符合 FMI”不等于数值/实时性已经验证。

## 4DOF/GNC 契约必须先做的对照表

拿到同事源码后，逐项填表；未填完不能进行代码转写：

| 维度 | 本项目现状 | 同事代码需确认 | 不一致时的风险 |
|---|---|---|---|
| 自由度/状态 | 常用 `[x,y,psi,u,v,r]`；controller ref 9 项 | 第四 DOF、`eta/nu` 排列、执行器/observer 状态 | 第四 DOF 被静默丢弃，或 controller 读错索引 |
| 控制输入 | 3 个广义量，典型 `[X,Y,N]` | rudder/rpm/azimuth 还是 force/moment；分配器位置 | PID 输出物理命令却被当成力，单位和闭环增益全错 |
| 模型调用 | 返回 `xdot`，外层 RK4 四次调用 | 内部 RK4 的 `step` 还是 derivative function | double integration、内部状态四次推进 |
| 坐标/单位 | 项目接口文档使用 NE/3DOF；运行时需统一 SI | NED/ENU、body/world、deg/rad、knots/m/s、正舵方向 | 反向转舵、横流符号错、ILOS 误差发散 |
| 环境 | `DisturbanceData` 有 wind/waves/currents 字段；模型实现需逐项确认 | 风浪流输入 frame、随机过程、wave spectrum/phase、相对速度 | 重复施加外力、风/流混用、无法复现 |
| 采样/状态 | `dt` 由 Simulator 传入，episode 有 reset | ROS timer、消息时间戳、内部 observer sample time | stale state、积分器增益随 dt 变化、重置后残留状态 |
| ILOS 输出 | guidance 目标是 `9 x N` pose/velocity/acceleration | course/heading、surge speed、sideslip/current estimate、rate/acceleration | 只传 heading 丢掉耦合前馈；路径段切换不一致 |
| 失败策略 | 本项目强调明确错误/不静默 fallback | 异常、NaN、消息超时、solver/observer failure 行为 | 故障时保持旧舵令，伪造成功轨迹 |

ILOS 不能只按“输出一个 heading”处理。原始 [Caharija 等 2016 IEEE 论文](https://doi.org/10.1109/TCST.2015.2504838)研究带积分 LOS 的欠驱动海洋船路径跟踪；[Fossen/Lekkas 的作者公开论文](https://www.fossen.biz/publications/2015%20Fossen%20and%20Lekkas%20IJACSP.pdf)说明 ILOS/adaptive LOS 用于补偿风、浪和流造成的漂移；公开的 [2024 IFAC 原始论文](https://doi.org/10.1016/j.ifacol.2024.10.024)特别强调 guidance 与 heading control 的耦合，以及由路径/LOS 生成 acceleration、rate-of-turn 和 heading setpoints。因此，调研结果支持把 `heading/course + surge + rate/acceleration + drift estimate` 的语义列为待核对项，而不是替用户选择某一 ILOS 变体。

复杂 PID/SMC/NDO 也必须视为带状态的闭环模块：PID 积分量、SMC reference model/sliding surface、NDO bias/velocity estimate、ILOS integral/current estimate、执行器实际状态都要进入 reset/trace 契约。官方 [PythonVehicleSimulator control.py](https://github.com/cybergalactic/PythonVehicleSimulator/blob/master/src/python_vehicle_simulator/lib/control.py)显示，PID 和 integral-SMC 都显式更新积分/reference-model 状态；这足以说明“同一公式 + 不同更新次序”会构成不同控制器。对于 NDO，可参考 Fossen/Strand 的原始 [Passive nonlinear observer design for ships](https://doi.org/10.1016/S0005-1098(98)00121-6)；论文摘要明确包含环境 disturbance/bias、速度估计和 wave filtering，但不能据此假定同事实现的 NDO 结构相同。

## 验证顺序（架构无论如何都需要）

1. **静态接口门槛。** 对每个模块检查 shape、dtype、有限值、单位、frame、版本和能力声明；拒绝未知维度，不以 reshape/截断“修复”4DOF。
2. **微分/力矩 oracle。** 在零风浪流、单一 constant input、单一 state 下，比对质量/附加质量/Coriolis/阻尼/恢复力/推进器/舵面/环境力的每一项，而不只比较总 `xdot`。
3. **积分器 parity。** 固定 `dt` 和四个 RK4 stage 输入，比较 C++ derivative、Python derivative 和一次 `x_next`；再做 `dt/2` 收敛测试。若使用 CS/FM​​U，分别验证通信点输出和内部步进。
4. **控制/GNC 单元测试。** 覆盖 angle wrap、低速、路径段切换、constant current、突变风浪、执行器饱和/速率限制、积分抗 wind-up、SMC boundary layer、NDO 初值和 `reset()`。每个测试保存内部状态和诊断。
5. **闭环短场景。** 先无 COLAV 单船直线/曲线路径，再加风、流、波和执行器动态；指标至少包括 cross-track、heading/course、surge/sway/yaw/roll、actuator command-vs-actual、observer error、环境力分量和实时因子。
6. **跨架构 replay。** 同一初始快照和环境 trace 分别运行 Python oracle、pybind、ROS2 bridge、FMU；比较时使用明确的时间/状态/输出容差，并记录编译器、commit、参数 hash、FMI/ROS/pybind 版本。
7. **系统故障与 COLAV 回归。** 注入 stale state、丢消息、QoS 不匹配、进程退出、非法 NaN、超时和 reset；确认故障显式暴露，不静默 fallback。随后分别报告模型/导引/控制本身指标和 COLAV 的安全指标，不把某次 closed-loop 通过称为模型验证。

## 可借鉴的官方仓库（不是直接依赖清单）

| 仓库 | 可借鉴内容 | 边界/许可 |
|---|---|---|
| [NTNU colav-simulator](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator) | 当前项目的 `Ship` 子系统契约、场景、传感器和 COLAV 验证边界 | MIT；它明确以 3DOF 典型接口为基础，不能直接假定支持同事 4DOF |
| [PythonVehicleSimulator](https://github.com/cybergalactic/PythonVehicleSimulator) | Python vessel object、PID/SMC、执行器、模型/控制/GNC 示例 | MIT；适合公式/测试参考，不是 ROS2 C++ 适配层 |
| [MSS](https://github.com/cybergalactic/MSS) | 3/6DOF 船模、风/波/流、RK4、GNC 和 hydrodynamic data 组织 | [MIT LICENSE](https://github.com/cybergalactic/MSS/blob/master/LICENSE)；MATLAB/Octave，不是 Python runtime |
| [CyberShip Software Suite](https://github.com/NTNU-MCS/cybership_software_suite) | NTNU ROS2 maritime simulate/visualize/control 的 ROS 包组织方式 | GPL-3.0；许可证及依赖必须隔离审查 |
| [ros2_control](https://github.com/ros-controls/ros2_control) | ROS2 controller manager、pluginlib、controller/hardware lifecycle 参考 | Apache-2.0；其机器人 joint interface 不是船舶 4DOF 力/舵/桨契约 |
| [FMI standard](https://github.com/modelica/fmi-standard) / [Reference-FMUs](https://github.com/modelica/Reference-FMUs) | ME/CS/SE 标准、headers/schema、FMU 交叉调试材料 | 标准文档 CC-BY-SA 4.0，随附 code/schema 2-Clause BSD；实际 FMU 依赖另查 |

## 交给同事代码前的最小资料包

需要同事提供（或从 AGS 路径读取后核对）：

- C++ commit/hash、ROS package 清单、`package.xml`/`CMakeLists.txt`、编译器和依赖版本；
- 4DOF 状态/输入/输出定义、坐标系/单位、质量/附加质量/阻尼/恢复力和环境力公式；
- 风浪流的生成器、随机种子、波谱/相位、采样方式和是否按相对速度计算；
- RK4、执行器、PID/SMC/NDO/ILOS 的调用顺序、内部状态、reset 和异常行为；
- 至少一组可独立运行的 C++ fixture：初态、参数、输入、环境 trace、逐 stage/逐 step 输出；
- ROS topic/service/action、消息定义、QoS、timer/executor、`use_sim_time` 和 launch 参数；
- 许可证、第三方依赖及是否允许复制/链接/二进制分发。

在这些资料齐全前，不应改动同事代码，也不应声称已经完成 4DOF/风浪流/PID-ILOS 的移植。下一步可先做只读源代码审计和契约对照，再由项目负责人选择先做 Python oracle、pybind11 适配、ROS2 bridge 或 FMU proof-of-concept。

## 来源范围

本文引用均为一手来源：ROS 2 官方 Humble 文档、pybind11 官方文档、FMI Modelica Association 标准/仓库、NTNU/官方作者维护的 MSS/PythonVehicleSimulator/Colav-Simulator/CyberShip 仓库，以及论文作者/出版方的原始论文页面。网页内容和仓库会更新；实施时应锁定具体 commit、ROS 2 distro、FMI revision 和 pybind11 版本。
