# Colav-Simulator 水动力、航行导引、航行控制模块集成调研

日期：2026-08-28

## 结论

本项目具备新增船舶模型、航行导引、航行控制实现的基础接口和闭环执行链，但不是“放入一个包即可自动发现”的通用插件系统。

- 航行控制：可直接适配，现有 `IController` 是明确扩展点。
- 航行导引：可直接适配名义航路跟踪；若要与现有 COLAV 同时串联，需调整当前“COLAV 或 Guidance 二选一”的规划边界。
- 水动力：可把同事的完整动力学模型适配为 `IModel`；若同事只提供水动力载荷/系数模块，当前没有独立 `IHydrodynamics` 接口，需要在一个新的 `IModel` 适配器内组合。
- Python 同进程模块最容易接入。C++ 可参考项目生态中的 pybind 方式。ROS 2、MATLAB/Simulink、独立进程模块需要新增桥接层，当前主链没有 ROS 2 节点/Topic 插件协议。

## 本地代码架构证据

### 闭环主链

```text
Simulator.step
  -> Ship.track_obstacles
  -> Ship.plan
       -> ICOLAV.plan 或 IGuidance.compute_references
       -> 9 x N references
  -> Ship.forward
       -> IController.compute_inputs(refs, state, dt)
       -> 3 元输入
       -> RK4(IModel.dynamics, IModel.bounds)
       -> 6 元船舶状态
```

关键源码：

- `colav_simulator/simulator.py:373`：统一执行跟踪、规划、前向积分。
- `colav_simulator/core/ship.py:567`：`Ship.plan()` 选择 COLAV 或 Guidance。
- `colav_simulator/core/ship.py:626`：`Ship.forward()` 调用控制器，再用 RK4 积分船模。
- `colav_simulator/core/integrators.py:17`：动力学函数被当作连续时间状态导数，单步调用四次。

### 现有扩展点

| 模块 | 接口 | 核心契约 | 当前内置实现 |
|---|---|---|---|
| 船舶/水动力模型 | `IModel` | `dynamics(xs, u, w) -> xdot`；`bounds()` | `KinematicCSOG`、`Viknes`、`RVGunnerus`、`CyberShip2` |
| 航行导引 | `IGuidance` | 航点 `2 x N`、速度计划、状态、`dt` -> 参考量 `9 x N` | LOS、Kinematic Trajectory Planner |
| 航行控制 | `IController` | 参考量 9、状态 6、`dt` -> 输入 3 | MIMO PID、FLSC、PassThroughCS、PassThroughInputs |

源码位置：

- `colav_simulator/core/models.py:342`、`:372`
- `colav_simulator/core/guidances.py:81`、`:114`
- `colav_simulator/core/controllers.py:171`、`:196`
- `colav_simulator/core/ship.py:153`、`:470`

`Ship(...)` 构造函数支持直接注入 `model`、`controller`、`guidance`。`tests/test_ship.py` 和 `tests/test_gunnerus.py` 已采用这种方式组合模型、控制器、LOS 导引。2026-08-28 本地复验：

```text
.venv/bin/python -m pytest -q tests/test_ship.py tests/test_gunnerus.py tests/test_simulator.py
9 passed, 1 skipped in 63.55s
```

### 已有水动力能力

`Viknes`、`RVGunnerus`、`CyberShip2` 已包含三自由度操纵动力学的质量/附加质量、科氏/向心项、线性或非线性阻尼。部分模型考虑风和海流。

边界：

- 波浪数据可由 `DisturbanceData` 进入仿真记录，但现有模型源码明确把波浪载荷列为后续增强；不能把“存在 waves 字段”当成已执行波浪水动力。
- `RVGunnerus` 内有推进器力计算代码，但当前动力学主链直接使用广义力 `tau`，推进器模型注释为未启用。
- 现有公共闭环实质固定在三自由度：状态 6、输入 3、参考量 9。六自由度模型不是直接替换。

## 集成限制

### 1. 接口存在，动态插件发现不存在

YAML 配置的 Builder 和 Cerberus schema 枚举具体实现名。新增可配置模块通常需要同时修改：

1. 模块实现或适配器；
2. 对应 `Config.from_dict()/to_dict()`；
3. `ModelBuilder`、`GuidanceBuilder` 或 `ControllerBuilder`；
4. `colav_simulator/schemas/scenario.yaml`；
5. 单元测试和至少一个闭环场景。

只做调试时，可先构造 Python 对象并注入 `Ship(...)`，暂不扩展 YAML。

### 2. `IModel` 还有隐式契约

接口表面只声明 `dynamics()`、`bounds()`；实际 `Ship`、控制器、COLAV 还读取 `model.params`，包括船长、船宽、吃水、最大速度、模型名，以及部分控制器所需质量/阻尼参数。适配器必须补齐这些属性。

同事模型若输出“下一状态”，不能直接接入；这里需要输出 `xdot`，由项目 RK4 完成积分。带内部积分器、推进器动态或随机状态的模型需避免在一次 RK4 的四次评估中错误推进内部时间。

### 3. Guidance 与 COLAV 当前互斥

`Ship.Config.from_dict()` 在 COLAV 和 Guidance 同时出现时保留 COLAV、清除 Guidance。运行时也是二选一：

- 名义航路调试：`IGuidance -> IController -> IModel`，可直接使用。
- 避碰算法直接输出航向/速度或轨迹参考：`ICOLAV -> IController -> IModel`，可直接使用。
- 若期望 `COLAV 输出新航路 -> 同事 Guidance 跟踪 -> 同事 Controller -> 同事 Model`，现有链条没有这个串联 seam；需要小范围重构或组合适配器。

### 4. 输入语义必须先冻结

当前控制边界默认三元广义力/力矩 `[X, Y, N]`，或为运动学模型传递 `[course, speed, 0]`。同事控制器若输出舵角、转速、方位角、油门，必须由同事模型直接接收这些执行器量，或新增执行器/推力分配适配层。不能仅靠数组长度相同判断兼容。

## GitHub 一手来源调研

### 1. NTNU `colav-simulator`：首选架构基线，不是额外依赖

仓库：<https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator>

这是当前本地项目的 upstream。其 README 明确：

- `Ship` 子系统通过 `IModel`、`IGuidance`、`IController` 等标准接口替换；
- 三自由度状态/输入/参考量契约为 6/3/9；
- 新模型的推荐步骤包括实现接口、参数类、Config、schema、测试；
- 支持运动学和动力学 GNC 组合，以及直接传递广义力的控制方式。

许可：MIT。适配度：最高。用途：同事模块的目标接口规范。

本地 `origin` 指向该仓库。远端 `main` 当前 SHA 为 `a385e0f...`；本地 HEAD `03987fc...` 在该基线上已有大量项目扩展，因此不能用覆盖式同步替代适配。

### 2. `PythonVehicleSimulator`：最适合纯 Python GNC/船模参考

仓库：<https://github.com/cybergalactic/PythonVehicleSimulator>

官方 README 列出纯 Python 的：

- `lib/control.py`、`lib/guidance.py`、`lib/gnc.py`；
- USV/船舶/AUV 模型，如 Otter、frigate、tanker、Clarke83；
- 每个 vehicle 对象组合 guidance、navigation、control 方法。

许可：MIT。2026-08-26 仍有推送记录。适配度：高。

建议用途：算法公式、参数、回归 oracle；把选定 vehicle/guidance/controller 分别包成当前项目接口。风险：其 vehicle 类通常把模型、执行器、控制逻辑组合在一起，需要拆适配层；坐标、状态、执行器输入必须逐项核对。

### 3. `MSS`：权威水动力/GNC 参考和数值 oracle

仓库：<https://github.com/cybergalactic/MSS>

MSS 包含 MATLAB/Octave 的 CRAFT、GNC、HYDRO、Simulink 目录；HYDRO 可处理 WAMIT/ShipX 数据、RAO、辐射力模型，GNC 提供 LOS、自动舵、DP 等示例。

许可：MIT。适配度：中等（研究/对照高，直接运行低）。

建议用途：公式、标准工况、数值对照。若同事代码本身来自 MATLAB/Simulink，先建立离线 parity oracle，再决定 Python 移植或进程桥接。不要把 MATLAB 引擎直接放进基础仿真步作为第一方案。

### 4. `mcsimpy`：高保真波浪/数字孪生候选，需隔离评估

仓库：<https://github.com/NTNU-MCS/mcsimpy>

项目定位为高保真船舶仿真模型的 Python 包，源自 MCSim_Python。README 同时明确声明：包不完整，模型有效性不保证。

许可：GPL-3.0。适配度：技术上中等，许可和验证风险高。

建议用途：波频/低频运动、波浪载荷、高保真模型的研究对照或隔离式适配。进入本项目主包前必须完成许可证评审、模型有效性验证、时间步性能测试。

### 5. `pybind_im_and_psbmpc`：C++ 同事模块的绑定范式

仓库：<https://github.com/ntnu-itk-autonomous-ship-lab/pybind_im_and_psbmpc>

该仓库不是水动力/GNC 库，但它是 upstream 生态为 C++ 算法提供 Python bindings 的官方实例。许可：MIT。

建议用途：同事模块若为 C++，参考其“原生库 -> pybind -> Python adapter -> simulator interface”路径。比在仿真主循环中新增临时 socket/子进程协议更贴近现有生态。

### 6. `Stonefish`：仅在明确需要 ROS/高保真物理平台时考虑

仓库：<https://github.com/patrykcieslak/stonefish>

Stonefish 是 C++ 海洋机器人仿真库，提供几何相关水动力和 ROS 集成。许可：GPL-3.0。

适配度：对当前 Python 三自由度闭环低。它更像替换/外接物理仿真平台，不是一个轻量 `IModel`。只有同事模块已基于 ROS，且目标是系统级 SIL/HIL，而非当前算法调试时，才值得单独设计桥接。

## 推荐集成路线

### 第一阶段：对象注入，验证同事模块本体

目标：不改 schema，不引入通用插件框架。

1. 冻结同事模块版本和许可证。
2. 为三类模块各写一个窄适配器，或确认同事实现已满足接口。
3. 用 `Ship(model=..., guidance=..., controller=...)` 直接组合。
4. 分层测试：模型导数/边界、导引参考量、控制输入、组合闭环。
5. 用无 COLAV、无目标船的航路跟踪场景先调通，再接避碰链。

### 第二阶段：配置化

对象注入通过后，再加 Config、Builder、scenario schema、能力目录/UI 暴露。每个 YAML 配置必须记录真实模块身份、版本和参数；缺依赖时应显式失败，不允许静默回退到内置模型/控制器。

### 第三阶段：COLAV 串联

先决定同事 Guidance 的位置：

- 若它只把航点变成航向/速度，保持 `IGuidance`；
- 若它处理目标船/ENC 并做避碰，适配 `ICOLAV`；
- 若必须接收 COLAV 输出的新航路，设计明确的 `RoutePlan -> Guidance -> References` seam，不能继续依赖当前互斥逻辑。

## 接收同事代码前必须收集的信息

- 语言、构建系统、依赖、许可证、固定 commit/tag；
- 三个模块是否独立，还是一个组合 GNC/船模对象；
- 坐标系、角度方向、单位、状态顺序；
- 模型输出是 `xdot` 还是 `x_next`；
- 控制输出是广义力，还是舵角/转速/方位角；
- 支持 3DOF 还是 6DOF；
- 模块调用周期、内部积分器、reset/seed 语义；
- 风、流、浪输入语义；
- 船体和执行器参数来源、标定场景、已知误差；
- 可提供的单元测试、回放数据、MATLAB/实船基准。

## 最终判断

适合接入，但应定义为“接口适配工程”，不是“新增三个目录”。最小风险路线：先用现有 Python 对象注入 seam 完成单船 GNC 闭环，再配置化，最后处理 COLAV 与 Guidance 串联。若同事代码满足 3DOF、Python、`xdot`、9/6/3 契约，工作量较小；若为 6DOF、ROS 2、MATLAB、执行器级输入或带独立积分时钟，需先设计桥接边界。
