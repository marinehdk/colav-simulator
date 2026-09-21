# ROS2 数字孪生平台选型与 MASS-L3 当前实现证据

日期：2026-09-17  
范围：Colav-Simulator（本地）→ ROS2 Humble MASS-L3（A4000 只读审计）→ 45 m FCB 数据采集与回放。  
性质：源码/官方文档证据与工程建议；没有实施集成，没有远程部署，没有把当前源码视为全链路验收。

## 结论先行

现有三步路线可行，但当前代码不是一条已经闭合的“Python → ROS2 L2/L3/L4/L5 → 45 m FCB”链路：

1. Colav-Simulator 已有可复现的模块化 GNC、环境、实验清单、决策轨迹和哈希回放；ROS2 适配器也有真实 `rclpy` 订阅类，但 G10 语义门主要由内存脚本传输覆盖，文件明确不声明真实 DDS/SIL/HIL 验收。
2. MASS-L3 同时存在两条船舶仿真候选路径。`src/sim_workbench/fcb_simulator` 是 45/46 m FCB 4-DOF MMG/RK4 的 L3-SIL 工具，直接订阅 M5 计划并内部做简化航向/速度控制；`third_party/gnc_ws` 的 GNC 仿真链则以 `/ship/odometry`、`/cmd_tau`、`/thruster/commands`、环境 Wrench 和 L4/L5 节点构成闭环，默认参数仍含通用/旧船尺度。两者不能只靠改 topic 名称直接拼接。
3. `gnc_bridge` 已提供较清晰的域 42（L3）↔域 50（GNC）边界、路线/避碰/重置/执行反馈和 QoS；它适合做 Step 2 的集成边界。生产路径仍需确认 L2、L4、L5 实际包版本和 FCB 设备接口。
4. 当前 SIL 有唯一 `/clock` 设计、场景重置屏障、MCAP/Arrow/Marzip 处理，但运行代码对 rosbag2 缺失存在开发机 PASS 旁路；A4000 主机本身没有 `ros2` 命令，不能把源码检查当作当前运行证据。
5. 当前 MASS-L3 的 AIS replay 能回放目标船，不等于能回放 45 m FCB 的 GNSS/IMU/舵桨/人机接管/雷达等实船数据。第三步必须新增“原始设备数据 + ROS2 话题 + 时钟关系 + 控制权 + 版本与校验”的统一数据包。

建议平台职责：Colav-Simulator 继续做场景、实验编排、评价和数据入口；ROS2 继续做生产软件集成面；Unity/ROS-TCP 只承担显示或成像仿真，Gazebo Fortress/`ros_gz`承担 ROS2 友好的 Plant/传感器仿真，FMI/OSP 只在需要接入黑箱动力学/推进/能源模型时引入。不要让三维引擎另起一套运动积分和环境载荷。

## 审计方法与快照边界

先调用本地 Colav-Simulator CodeGraph，探索 `integrations`、`modular_gnc/ros_adapter`、实验回放和 ROS2 运输边界；CodeGraph 返回的当前源码作为首轮读取证据。随后用文件行号核对本地关键文件。对 MASS-L3 尝试使用 CodeGraph 时，工具返回“项目未索引”，之后停止对该项目调用 CodeGraph，改用 SSH 只读文件检查，符合项目自身 `AGENTS.md` 的规则。

MASS-L3 当前可访问快照：

```text
host: a4000 / user: marine.huang
path: /home/marine.huang/Code/mass-l3
HEAD: fa7635af53fce5e3cca18dcc5f8c484032a65aca
branch: fix/207-ot-nav-mode7
dirty: docker/sil_entrypoint.sh（审计未修改）
```

本地 `/Users/marine/Code/MASS-L3-Tactical Layer` 不存在；旧对话或记忆中的本地路径不能当作当前代码事实。远端 `AGENTS.md` 指定架构为 `L1 Mission → L2 Voyage → L3 Tactical → L4 Guidance → L5 Control`，并要求把实现、独立审查、部署和运行验收分开记录（`/home/marine.huang/Code/mass-l3/AGENTS.md:1-31, 60-91`）。

## Colav-Simulator 当前可复用面

### 真实 ROS2 seam 存在，但 G10 不是 A6 证据

`colav_simulator/modular_gnc/ros_adapter.py` 的模块文档明确写出：核心栈、规划器和 Plant 不导入该适配器，适配器只把运输流转换成带仿真 tick 的输入；ROS2 是可选依赖，G10 语义由 `ScriptedCommandTransport` 覆盖，声明不包含真实 DDS、ROS2 runtime 或 HIL（`ros_adapter.py:1-26, 66-72`）。

代码同时提供 `Ros2CommandTransport`：构造时懒加载 `rclpy`，将类型化 QoS 转成 `rclpy.qos.QoSProfile`，由调用方提供 node、消息类型和消息转换器，再创建真实订阅（`ros_adapter.py:707-747, 750-778`）。当前类的 `peer_process_lost` 和 `peer_reset_reported` 固定返回 `False`，所以“有真实订阅类”不能升级为“具备生产级进程存活与重置检测”（`ros_adapter.py:780-797`）。

这给 Step 2 一个合适的最小增量：保留 `CommandTransport` seam，新增真实 MASS-L3 消息适配器、DDS liveness/Reset 合同和实际节点/Plant 验收；不要把 G10 通过当成 ROS2 闭环通过。

### 实验、决策记录与确定性回放已较完整

`decision_replay/recorder.py` 会在运行中写入全量 frame 和事件，并沿用 `TraceSink` 与实验 `RunSpec`（`colav_simulator/decision_replay/recorder.py:1-8, 27-63`）。`ExperimentRunner` 在 finalize 时写轨迹语义哈希和事件；`replay()` 重新执行原 `RunSpec`，比较 episode hash 与 trajectory semantic hash，不一致就失败（`colav_simulator/experiment/runner.py:857-865, 905-935`）。

这些能力可直接成为三阶段共用的证据骨架，但实船数据需要扩展数据源身份、设备时间、接收时间、控制权与原始文件校验，不能只把设备轨迹塞进现有 `trajectory`。

## MASS-L3 当前代码审计

### A. FCB simulator：适合 Step 1/局部 SIL，不是现成 L2-L5 Plant

`src/sim_workbench/fcb_simulator/README.md` 将它定义为 FCB 4-DOF MMG、RK4、L3 Tactical Layer 的 HIL/SIL 工具，状态为 `[x,y,psi,u,v,r,phi,phi_dot]`，参数说明为 46 m FCB 的工程初值；README 同时注明参数待倾斜/海试校准，当前只适合 SIL（`README.md:3-20, 22-35, 56-67`）。

节点目前：

| 面 | 源码证据 | 现状含义 |
|---|---|---|
| 输入 | `fcb_simulator_node.cpp:43-48` | 订阅 `/l3/m5/avoidance_plan`、`/l3/m5/reactive_override_cmd` |
| 输出 | `fcb_simulator_node.cpp:50-64, 182-228` | 50 Hz `/fusion/own_ship_state`、2 Hz `/fusion/tracked_targets`；目标默认为空 |
| 控制 | `fcb_simulator_node.cpp:146-180` | 节点内部用简化比例航向/速度控制，把 M5 waypoint 转成 rudder/propeller，再调用 MMG plugin |
| 动力学接口 | `ship_motion_simulator.hpp:29-41`、`fcb_simulator_plugin.cpp:32-46` | `step(state, delta, n_rps, dt)`；另有 FMI 2.0 变量枚举 |
| 环境输入 | `fcb_simulator_plugin.cpp:67-74` | FMI 描述列出 wind/current 输入，但节点实际 `step` 只传 rudder、propeller 和 dt；环境话题到模型的闭环尚未形成 |
| 参数可信度 | `fcb_dynamics.yaml:5-6, 13-18, 43-45, 67-78` | 数值明确标记 `HAZID-UNVERIFIED`，不能当作真实 45 m FCB 校准模型 |

因此它可作为 Step 1 的“Colav/ROS2 旁路状态展示 Plant”，但若 Step 2 要接同事真实 L4/L5，至少要定义一条从 L4/L5 `/ship/waypoints`/heading-speed 或 `/cmd_tau` 到 FCB 执行器的单一控制边界，并把环境载荷、执行器反馈、重置和时间推进补齐。

### B. 第三方 GNC 仿真链：接口更接近 L2-L5，但船模与 FCB 配置必须先对齐

`third_party/gnc_ws/src/platform/ship_bringup/launch/sim_launch.py` 将 ship dynamics、thrust allocation、风/流 engine、force aggregator、ship guidance、coordinate transform、active route manager、ship control 和 robot state publisher 放到同一 ROS2 launch；它还在 `use_sim_time=true` 时拒绝 `time_scale != 1.0`，防止双重时间缩放（`sim_launch.py:75-130, 176-240, 253-325, 328-398`）。

实际消息链如下：

```text
/route_planning/route_plan (L2)
        ↓ coordinate_transform / active_route_manager
/ship/waypoints, /gnc/active_route
        ↓ ship_guidance
/control/heading_setpoint, /control/speed_setpoint
        ↓ ship_control
/cmd_tau
        ↓ thrust_allocation
/thruster/commands
        ↓ ship_dynamics
/ship/odometry + /ship/heading
```

关键源码：

- L4 `ship_guidance_node.cpp:470-500` 订阅 `/ship/odometry`、`/env/total_load`、`/env/current_load`、transient-local `/ship/waypoints`，发布 heading/speed setpoint，并使用 wall timer。
- L5 `ship_control_node.cpp:58-83` 订阅 odometry、target pose、heading/speed setpoint，发布 `/cmd_tau`，同样用 wall timer。
- L5 allocation `thrust_allocation_node.cpp:166-203` 订阅 `/cmd_tau`、环境 Wrench、odometry、健康/约束和 reset，发布 `/thruster/commands`。
- Plant `ship_dynamics_node.cpp:153-212` 订阅 `/env/total_load`、`/thruster/commands`、`/ship/waypoints`、`/ship/dynamics_reset`，发布 `/ship/odometry`，通过 wall timer 驱动物理。
- Plant `ship_dynamics_node.cpp:512-519` 的 reset 将位置回到 `(0,0)`，只从 `ShipReset` 读取 heading/SOG；`update_dynamics()` 用实测 wall dt 乘 `time_scale`（`ship_dynamics_node.cpp:633-654`）。

这条链比 `fcb_simulator` 更适合接生产 L4/L5，但不能直接称为 45 m FCB 真模型：运行时配置、推进器布局、质量/惯量、阻尼和速度限值必须与 FCB 实船资料对齐；同时必须把 wall-timer/time-scale 行为改造成可验证的实时或显式 lockstep 模式，才适合 pause/seek/反事实回放。

### C. L2 外部接入与 L4 SIL adapter 已有，但存在两套语义

外部 L2 route adapter 在 `src/sim_workbench/external_adapters/external_adapters/l2_route_plan_adaptor.py:116-167` 订阅 `/route_planning/route_plan`，用 reliable + transient-local QoS 缓存到 lifecycle ACTIVE 后转发；`tdl_ingress_node.py:48-114` 则以 TCP 8765 接收 targets/ownship/environment/route_in，发布 `/fusion/*` 和 `/l2/planned_route`。

SIL L4 adapter 在 `l4_guidance_adapter/node.py:68-92, 130-187` 使用 best-effort volatile 传感器面、reliable transient-local 路线面、reliable volatile 避碰面，发布 `/sil/actuator_cmd`；它明确注释 production GNC 使用独立 `gnc_bridge` 路径（`node.py:1568-1577`）。这说明 SIL adapter 可作为行为测试面，但不能替代生产 L4/L5。

### D. 当前 replay 主要是 AIS 目标级数据

`src/sim_workbench/ais_twin/ais_twin/store.py:17-76` 的数据集产物是 `raw.jsonl`、`tracks.csv` 和 manifest，轨迹字段集中于 MMSI、时间、经纬度、SOG、COG、heading；`src/sim_workbench/ais_twin/ais_twin/replay_node.py:63-80` 只发布 `/fusion/tracked_targets`。另一条 `src/sim_workbench/ais_bridge/ais_bridge/replay_node.py:13-75` 读取 NOAA/DMA AIS 并发布目标数组。它们可作为目标交通回放输入，但没有本船 GNSS/IMU、舵桨反馈、船长接管、雷达/相机原始数据或设备时钟合同，不能直接满足 Step 3。

### E. `gnc_bridge`：当前最有价值的 Step 2 seam

`gnc_bridge` 的 L3 side（域 42）订阅：

- `/l3/m5/avoidance_plan`；收到后校验 confidence，再排队跨域；沉默超过 60 s 有 wall watchdog（`gnc_bridge_node.cpp:138-168`）。
- `/l2/planned_route`，transient-local；`/l3/sim/reset_own_ship`，reliable + transient-local；`/l3/m7/heartbeat` best effort；`/clock` 只给 MRM staleness 专用 clock；`/l3/m7/mrm_command` reliable + transient-local（`gnc_bridge_node.cpp:169-197, 207-234, 236-285`）。

GNC side（域 50）订阅 `/ship/geo_position`、`/gnc/route_execution_status`、`/gnc/execution_odd`、route status 和 accepted snapshot；发布 `/colav/avoidance_plan`、`/route_planning/route_plan`、`/ship/geo_origin_reset`、`/ship/dynamics_reset`、`/gnc/mrm_speed_command`（`gnc_bridge_node.cpp:688-763`）。L3 publisher side 再发布 `/sil/own_ship_state`、`/l3/gnc/execution_status` 和 execution ODD/route receipts（`gnc_bridge_node.cpp:955-1040`）。

其 reset fanout 是可复用的：`/l3/sim/reset_own_ship` 进入 bridge 后，发布 `/ship/geo_origin_reset` 和 `/ship/dynamics_reset`（`gnc_bridge_node.cpp:925-932`）。但跨域队列、coalescing、drop budget 和 MRM/gate-hold 都是生产安全语义，不能通过外部 TCP adapter 绕过。

## 时间、QoS、rosbag2 和回放陷阱

### 一个 `/clock` 权威与两个时钟域

ROS 2 官方时间设计规定：`use_sim_time` 激活时，ROSTime 取 `/clock`；没有首个样本时读到 0；向后跳变需要清理状态；`/clock` 频率/粒度由应用决定（[ROS 2 Clock and Time](https://design.ros2.org/articles/clock_and_time.html)）。

MASS-L3 当前 `sil_lifecycle` 把 `/clock` 和 `/sim_clock` 作为 lifecycle manager 的输出：

- on_activate 创建两个 publisher，并在跨运行时复用 publisher instance，避免 transient-local stale cache（`sil_lifecycle/lifecycle_mgr.py:855-895`）。
- activate 前检查 DDS 中 `/clock` publisher 数量，超过 1 就拒绝；每 15 s 重新检查（`lifecycle_mgr.py:403-407, 544-597, 870-876, 995-1005`）。
- realtime 模式按 wall elapsed × sim rate 逐 tick 发布；catch-up 单次上限 50 tick（`lifecycle_mgr.py:1321-1368`）。
- free-run 模式还会以 TCP lockstep 等待客户端 ACK（`lifecycle_mgr.py:1121-1290`）。

不要同时运行旧 `third_party/gnc_ws/src/simulation/sim_clock/src/sim_clock_node.cpp`：该节点自己以 50 Hz 发布 `/clock`、默认 `time_scale=10.0`、使用 wall timer（`sim_clock_node.cpp:15-49`），会违反当前“单一 clock authority”约束。

域 50 的 `gnc_bridge` 节点保持 wall semantics，只有 MRM staleness 面订阅域 42 `/clock` 并使用专用 `RCL_ROS_TIME` clock；这不是把整个 GNC 域切到 `use_sim_time`（`gnc_bridge_node.hpp:103-129, 851-865`，`gnc_bridge_node.cpp:236-260`）。Step 2 必须把“仿真软件时钟”和“GNC 生产 wall clock/专用 MRM 映射”分别写入接口字典。

### QoS 不匹配会静默断链

ROS 2 官方 QoS 规则：publisher 的 best effort 与 subscriber 的 reliable 不兼容；volatile publisher 与 transient-local subscriber 不兼容；要让 late joiner 收到 latched sample，双方都要 transient-local（[ROS 2 QoS](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html)）。

当前代码已有容易被接错的组合：MASS-L3 L4 `avoidance_plan` subscriber 是 reliable volatile，而 `fcb_simulator` 用整数 depth 的默认 publisher；external route 用 reliable transient-local；L4 route 与 MRM 又要求 transient-local。每个话题应冻结：类型、publisher QoS、subscriber QoS、频率、deadline/lifespan、stamp clock、late-join 语义、reset/expiry 语义，并用 `ros2 topic info --verbose` 或真实 test node 验证。

### rosbag2/MCAP 版本与控制语义

官方 rosbag2 当前说明：可记录/回放带时间戳消息，`--use-sim-time` 使 recorder 用最近 `/clock` 给记录打时间戳；player 支持 pause、resume、seek、rate、play-next 等 service；播放 `--clock` 时，`/clock` 只在 playback session active 时发布，暂停时固定频率更新停在暂停时间（[rosbag2 README](https://github.com/ros2/rosbag2)）。这些 rolling 文档不能自动等价为本地 Humble patch level，部署镜像必须锁定并实测。

MCAP storage plugin 官方说明支持 `ros2 bag record/play/info -s mcap`；`fastwrite`/无 message index 会影响按 topic 读取和 seek，不适合作为长期归档默认配置（[rosbag2_storage_mcap README](https://github.com/ros2/rosbag2/blob/rolling/rosbag2_storage_mcap/README.md)）。ROS2 Humble 兼容宏在 rosbag2 MCAP CMake 中标为 0.15.x；A4000 apt cache 当前候选是 `0.15.17-1jammy.20260908.085225`，但未安装且 `ros2` CLI 不在 A4000 host PATH，因此这是版本线索，不是 runtime PASS。

仓库内的当前证据链：

- `docker/sil_nodes.Dockerfile:6,23-39` 基于 `ros:humble-ros-base`，安装 `ros-humble-rosbag2` 和 `ros-humble-rosbag2-storage-mcap`。
- `src/sil_orchestrator/marzip_builder.py:25-69` 用 `rosbags` Humble typestore 读取 `/sil/scoring`、`/sil/own_ship_state`、`/sil/asdr_event`；`205-218, 243-253` 组装 MCAP、Arrow、ASDR、manifest 和 SHA256。
- `tools/vv/mcap_to_arrow.py:19-34, 42-98` 只抽取固定 topic，并按原始 timestamp 写 Arrow；目标船、传感器原始流和 FCB actuator 需要扩展 topic 白名单/类型映射。
- `gate_runner.py:618-645` 把 `/clock`、rosbag2、ASDR 纳入 Gate 5，但 `_check_rosbag2_ready()` 在无 ROS2/开发机时返回 CHECK_OK 旁路（`gate_runner.py:714-737`）。这只能说明开发环境容错，不是记录链完整性验收。

### reset、pause、seek 不能只靠 rosbag2

rosbag2 player 的 seek 服务只移动播放位置；不会自动清理 L3/L4/L5 的缓存计划、PID/积分、MRM latch、route progress 或 Plant 状态。MASS-L3 已有补救结构：

- L4 收到 `/sil/scenario_loaded` 后只置 pending flag，在 autopilot timer 内执行 deferred reset；收到 ownship sim time 向后跳变也 reset（`l4_guidance_adapter/node.py:183-187, 450-467, 1492-1504`）。
- `lifecycle_bridge` 在 GNC profile 下先发布 `/l3/sim/reset_own_ship`，等待 `/sil/own_ship_state` 读回位置/航向/SOG，再发布 `scenario_loaded`（`lifecycle_bridge.py:650-666, 998-1035`）。
- lifecycle activate 会重发 fresh `/clock`/`/sim_clock` 和 status，避免 transient-local 上一个 run 的时间缓存（`lifecycle_mgr.py:1011-1023`）。

Step 3 的标准回放顺序应是：停止/暂停 player → 清除旧运行 → 建立唯一 clock → Plant/GNC reset barrier → 确认首帧状态 → 再播放或 seek；每次向后跳时记录 time-jump event。对真实船在线运行，不启用仿真 `/clock`，保留设备原始时间与系统接收时间。

## 平台选型比较

| 方案 | 官方事实与版本边界 | 对三阶段的合适位置 | 主要风险 |
|---|---|---|---|
| Unity + ROS-TCP Connector | Unity 官方仓库提供 `ROSConnection`、消息生成、可视化和 ROSGeometry；README 要求 Unity 2020.2+，可用 tag 或 main 安装（[官方仓库](https://github.com/Unity-Technologies/ROS-TCP-Connector)）。Unity Robotics Hub 的 ROS2 教程通过 ROS-TCP-Endpoint 和生成的 C# 消息连接 ROS2（[教程](https://github.com/Unity-Technologies/Unity-Robotics-Hub/blob/main/tutorials/ros_unity_integration/setup.md)）。 | Step 1 的三维显示、相机/雷达成像原型；ROS2 全链路的观察端。 | TCP endpoint 不是 DDS；需要自建时间/暂停/重置/大消息背压和 QoS 映射；本方案由外部 Plant 负责运动积分，Unity 不拥有安全仲裁权。 |
| Gazebo Fortress + `ros_gz` | 官方迁移文档明确 Fortress 是 ROS2 Humble 正式配对版本；`ros_gz_bridge`/`ros_gz_sim` 提供 topic bridge 与 launch/spawn 工具（[官方迁移文档](https://gazebosim.org/docs/all/migrating_gazebo_classic_ros2_packages/)，[ROS2 bridge](https://gazebosim.org/docs/fortress/ros2_integration/)）。 | Step 2 的 ROS2 友好 Plant、传感器和环境仿真基线。 | bridge 只支持部分消息类型；需将 MASS-L3 custom IDL 映射到 Gazebo transport；45 m FCB、风浪流、执行器模型仍需校准。 |
| VRX | OSRF 官方 Wiki 将其定义为 USV autonomy framework；Release 3 默认 Gazebo Sim Harmonic + ROS2 Jazzy（[VRX Wiki](https://github.com/osrf/vrx/wiki)）。旧教程仍展示 ROS2 Humble Docker（[Humble tutorial](https://github.com/osrf/vrx/wiki/tutorials-vrx_docker_interactive)）。 | 需要海事世界、USV 任务/基准和可复用场景资产时作为 Gazebo 上层参考；新项目接受 Jazzy 时再考虑直接采用。 | 当前默认 Jazzy/Harmonic 与 MASS-L3 Humble/Fortress 不同；Humble 回移和版本锁定需要单独维护，不应默认为无缝兼容。 |
| FMI 2.0 + OSP/libcosim | FMI 定义 XML、binary、C code 的模型交换容器（[FMI 官方](https://fmi-standard.org/)）；OSP-IS 是 FMI 2.0 co-simulation 的语义扩展（[OSP-IS](https://opensimulationplatform.com/specification/)）；libcosim 提供固定步 master、模型步长倍数约束、日志和分布式 co-simulation（[libcosim](https://open-simulation-platform.github.io/libcosim)）。 | Step 1/2 接入船体、推进、能源或厂商黑箱 FMU；Step 3 用同一 FMU 做离线对照。 | FMI 不定义 ROS2 topic/QoS/控制权/船载安全；需要 ROS2 mediator。当前 MASS-L3 `fmi_bridge` 只有 contract/parser 级实现，不能声称已运行 libcosim。 |
| Gemini / PyGemini | [Gemini 官方仓库](https://github.com/Gemini-team/Gemini) 已归档，旧适配器是 ROS1，详见同日 NTNU 专项报告；海事 PyGemini 本次未找到可核验的官方安装版本。 | Gemini 可作为需自维护的显示/传感器候选；PyGemini 保留研究评估。 | 二者都不能仅凭论文视为已完成本项目 ROS2 Humble 集成；需冻结版本、构建、资产并实测。 |

### 当前 `fmi_bridge` 的实现边界

仓库 README 将 `fmi_bridge` 描述为 ROS2 Humble DDS ↔ FMI 2.0 bridge，Phase 1 是 pythonfmu，Phase 2 才是 C++ FMI Library（`src/sim_workbench/fmi_bridge/README.md:1-34`）。但 `libcosim_wrapper.cpp:28-114` 只解压并解析 `modelDescription.xml`；`run_for()` 仅递增 `current_time`，`get_real()/set_real()` 只读写内存 map（`libcosim_wrapper.cpp:120-145`）。`dds_fmu_bridge.cpp:25-43` 订阅/发布的实际类型固定为 `std_msgs/msg/Float64`，不能消费配置中的自定义 `msg_type`/`field_map`；节点 `dds_fmu_node.cpp:36-48` 以 wall `rclcpp::Rate` 循环。

因此 FMI/OSP 在总体架构上值得保留，但当前代码要先完成真正 FMU lifecycle、variable exchange、typed ROS2 mapping、reset/rollback 和 fixed-step master，再进入 Step 2 验收。

## 推荐的三阶段落地合同

### G0：先冻结四类合同

1. **Plant 合同**：只有一个运动积分权威；输入环境、执行器命令、扰动、reset；输出真值和传感器观测。
2. **ROS2 合同**：topic/type/QoS/frequency/stamp clock/expiry/ownership；域 42/50 与桥接方向固定。
3. **时间合同**：模拟 `/clock`、GNC wall clock、设备时间、接收时间和回放时间映射分开；向后跳变处理方法固定。
4. **证据合同**：run id、scenario/model/algorithm commit、container digest、IDL/schema hash、MCAP metadata、原始文件 SHA256、评价配置和人工事件标注同包保存。

### G1：Colav-Simulator + 显示后端

- 首个切片只接本船/目标状态、计划/预测轨迹、环境向量、控制权和事件，不把 Unity/Gazebo 的 Plant 接管混入。
- 开/关显示、暂停/倍速、相同 seed 必须保持数值轨迹和事件在声明容差内一致。
- 展示必须覆盖监视、避让、通过、恢复；报告原始安全、COLREG 行为、任务和 solver/fallback 身份。

### G2：真实 ROS2 L2/L3/L4/L5 + FCB Plant

- 先用实际包和 commit 做 topic/QoS/clock/reset smoke，再跑完整闭环。
- 生产路径必须经 `gnc_bridge` 和唯一执行器命令仲裁；SIL `l4_guidance_adapter`、TCP route adapter、脚本 publisher 只能作为标记清楚的联调替身。
- 以 `third_party/gnc_ws` 链为 L4/L5 参考时，先完成 FCB dynamics/actuator/environment interface adapter；以 `fcb_simulator` 为 Plant 时，先消除其内部 M5-direct autopilot 与生产 L4/L5 的双重控制。
- 验收包含真实 DDS discovery、QoS compatibility、/clock 单权威、暂停/恢复/重置、进程丢失、route/avoidance TTL、MRM/gate-hold、端到端执行反馈和 wall-clock deadline。

### G3：真船数据与反事实回放

- 真实船在线记录不发布仿真 `/clock`；用系统时间/设备时间双时间轴记录。rosbag2 MCAP 作为 ROS2 通道归档，原始雷达/视频/控制器文件作为旁路 artifact，二者以同一 run manifest 和 clock map 关联。
- 先做航行重现，再做传感器/决策 shadow；只有 Plant/执行器模型经过独立航次留出验证后，才允许反事实闭环。
- 回放每个分支先 reset barrier，再播放；禁止用每个采样点强行贴实船位姿来掩盖模型漂移。
- 模型版本、参数适用域、训练/调参/留出航次、残差和不确定性进入 manifest；未经独立留出验证，不把参数更新回控制基线。

## 未解决输入与下一次现场核查

以下事项不应由旧对话或当前候选代码代填：

- 同事 L2/L4/L5 的实际包名、commit、ROS distro、接口/频率/QoS 和是否使用 wall timer；
- 45 m FCB 实船的实际质量/惯量/吃水/装载、推进器/舵机反馈、环境传感器和控制权记录权限；
- GNSS/IMU/雷达/相机/控制器的原生时间、时钟同步方式、可导出的原始格式和磁盘预算；
- 是否有经批准的辨识操纵（加减速、左右转、zig-zag、停船）以及试航安全限制；
- ROS2 Humble 镜像内 `rosbag2_storage_mcap` 的确切包版本、RMW、QoS override、`ros2 bag play` services 在目标容器中的实际行为；
- Unity/Gazebo/VRX 是否已有许可、船模、传感器资产和维护责任人。

## 官方一手资料索引

- [ROS 2 Clock and Time](https://design.ros2.org/articles/clock_and_time.html)
- [ROS 2 Humble QoS settings](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html)
- [rosbag2 upstream README](https://github.com/ros2/rosbag2)
- [rosbag2 MCAP storage plugin](https://github.com/ros2/rosbag2/blob/rolling/rosbag2_storage_mcap/README.md)
- [Gazebo Fortress ROS2 integration](https://gazebosim.org/docs/fortress/ros2_integration/)
- [Gazebo migration and Humble/Fortress pairing](https://gazebosim.org/docs/all/migrating_gazebo_classic_ros2_packages/)
- [VRX official Wiki](https://github.com/osrf/vrx/wiki)
- [Unity ROS-TCP Connector](https://github.com/Unity-Technologies/ROS-TCP-Connector)
- [Unity Robotics Hub ROS2 setup](https://github.com/Unity-Technologies/Unity-Robotics-Hub/blob/main/tutorials/ros_unity_integration/setup.md)
- [FMI official standard](https://fmi-standard.org/)
- [OSP Interface Specification](https://opensimulationplatform.com/specification/)
- [OSP libcosim](https://open-simulation-platform.github.io/libcosim)

## 证据等级

- **源码读取**：路径与行号来自本地 checkout 或 A4000 `/home/marine.huang/Code/mass-l3` 当前快照；不代表代码已在本轮运行。
- **官方文档**：平台/标准/版本语义来自上方一手链接；rolling 文档描述不自动等同于 Humble 已安装行为。
- **运行核查**：本轮只做 A4000 host 的路径、git 状态和 apt cache 只读检查；未启动 ROS2、未录制/播放 bag、未部署、未改远端。
