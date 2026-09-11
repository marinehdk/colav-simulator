# 原版 GNC 嵌入保真报告
状态：最终 v8 已完成数学、模块/边界、70 格嵌入运行与两组共同调度闭环；全长固定输入 28/28 与追加 3 个种子已通过各自预定门。自由异步闭环差异及产品场景失败单列，不扩大保真结论。

## 实现与来源边界

固定源 183 文件；清单 SHA256 `2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`。最终本地动态库 SHA256 `6e9f2728758b7934296e8da9bfee1a98905e038b29402c6e95ae780c6dc220fa`。本报告只约束该候选和记录过的工具/输入哈希，不泛化为任意编译器、操作系统或实船资格。

六个核心原 C++ 类：coordinate_transform、active_route_manager、ship_guidance、ship_control、thrust_allocation、ship_dynamics；四个环境原 C++ 类：wind、current、wave、force_aggregator；四个原 Python 业务模块：propulsion_policy、navigation_mode_observer、operational_risk_observer、operator_command_interpreter。ROS 传输、Node 外壳替换成显式时钟/参数/类型化 FIFO 发布端口，保留原业务函数、状态、方程、保护及周期。原 launch 未启用的融合、NDO、mission/safety 主链没有凭名称补启用。

构建校验每个冻结文件和资产，记录提取来源及变换。Python 构建时抽取原业务类；C++ 生成文件在 build 中，未把整个外部平台纳入仓库。本地库只链接 libc++/libSystem，运行不需 ROS2 或 A4000；仍需要冻结源资产、匹配构建和本机依赖。缺失时不可用，不 fallback。

[构建与导出身份](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/build-manifest.json)；[逐模块提取台账](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/extraction.json)；[构建说明](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/cpp/original_gnc/README.md)。
## 跨平台数值修正台账

没有修改 PID 增益、PGD 容差、路线保护、物理方程或 case 来求 PASS。定位后修正运行基底：

| 来源差异 | 处理 | 验证与限制 |
|---|---|---|
| GCC/Eigen 乘加次序与 Apple clang 不同 | 局部固定非收缩次序 | 实际包装库 RHS/RK 与独立原源码 probe |
| libstdc++ / libc++ 正态采样成对返回顺序 | 保留原标准库的取样顺序 | 环境 RNG 状态及逐回调输出 |
| Darwin trig/hypot 与 glibc 数 ULP 差，经 PGD 放大 | 本库内使用原 GNU 算法及对应 contraction profile | 独立 seeded primitive probe；符号隐藏，不劫持全局 libc |
| 原 GCC 单独 sin/cos 与配对 sincos 的算术路径不同 | 分别保留对应 FMA 语义，含 Apple 配对调用入口 | R05 全长零差；R06-E4 累计漂移降至毫米级 |
| allocator exp 的实现路径 | 独立 Arm/glibc FMA helper | 固定输入分配向量与实际库比对 |
| 原 R1 警告日志限流导致纯显示 `now()` 是否执行不同 | 只在原日志显示位置消费记录的 clock；业务时钟不跳过 | R09-E4 失败原证据保留，修订 driver 原显示块之外 SHA 不变 |

GNU 原始文件原样保留及 LGPL 声明；Arm exp 保留 MIT。见[数学实现来源及许可证](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/cpp/original_gnc/reference_math/GLIBC-NOTICE.md)。早期 v2–v7 的失败构建与比较文件保留，未覆盖为成功。
## 比较层次与固定门

R0 是原生异步 ROS 节点；R1 是独立编译原源码按 R0 记录的输入、回调顺序和时钟进行逐模块回放；E 为本地提取版。先验 R0→R1，再验 R1→E，不能用未经自验的参考驱动证明保真。合并 R09 的十模块证据仍是逐模块固定输入回放，不冒充一套整体 ROS graph 的加速闭环。

同输入门不放宽：位置 atol 1e−6 m/rtol 1e−10，速度 1e−8 m/s/1e−9，角度 1e−8 rad，角速度 1e−9 rad/s/1e−9，力 1e−3 N/1e−8，力矩 1e−2 N·m/1e−8；内部状态按物理单位固定规则。枚举、段号、ID/版本、布尔、原因类别、事件序列和内部 tick 精确一致。缺字段、漏事件、非有限数的错误位置/语义不被填零或忽略。完整规则和实际比较器 SHA 记录在每份 comparison。

发布连续量报告各单位最大误差；内部状态逐字段判定，未额外声称已给出状态全分位统计。离散内容逐字段校验；可打印 JSON/状态里的合法非有限哨兵按明确 schema 比较，不把任意 NaN 当相等。实际 ROS 序列化比较器另经 7 个负例验证：包括同字节畸形 payload 必须拒绝，只有 padding 差异的合法消息须按解码内容比较。

## 定点、数学与边界覆盖

| 组 | 调用/字段数量 | 结果 | 证据 |
|---|---:|---|---|
| reference_vectors | 10315 callbacks | True | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/validation-reference_vectors/comparison.json) |
| reference_env_vectors | 12992 callbacks | True | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/validation-reference_env_vectors/comparison.json) |
| reference_boundary_vectors_v2 | 1608 callbacks | True | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/validation-reference_boundary_vectors_v2/comparison.json) |
| reference_route_contract_vectors | 3803 callbacks | True | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/validation-reference_route_contract_vectors/comparison.json) |
| reference_route_boundary_vectors | 32 callbacks | True | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/validation-reference_route_boundary_vectors/comparison.json) |
| route boundary v2 | 43 callbacks | True | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/route-boundary-validation-v2/comparison.json) |
| 船体 M/M inverse/C/D/RHS/RK | 936 probes / 90,792 scalar fields，全部零差 | PASS | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original-math-native-probe-glibc-v8/comparison.json) |
| 原推进策略 | 110 calls / 34 publications / 181 clocks | PASS | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/glibc-v8-policy-validation.log) |
| 三个原观察器 | 250 / 400 / 520 calls | PASS | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/glibc-v8-observer-validation.log) |

物理 probe 的 M 来自实际对象，原始 RHS/RK 直接调用最终动态库。C/D 为原表达式分解并与实际 RHS 核对，未声称截获原函数中的所有局部矩阵。状态覆盖包括控制积分/前误差/导数/模式、导引积分/段/DP latch、分配上一执行器值/健康/限幅、船体 eta/nu/执行器/载荷、环境 RNG 及谱/滤波状态；逐字段访问表见[state_fields.py](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/tools/original_gnc/state_fields.py)。这是明确列出的观测字段集合，不是穷尽所有内部变量。
路线边界覆盖原 10 s 更新保护及 5 s 请求、版本/父路线、过期、取消、恢复、异常/缺失请求。补测真实 500 m 首变化距离及 manager 30 m 段长两侧：投影 499.999998999 m 拒绝；名义 500 m 实算 499.9999999985 m 仍拒绝；500.00000100027 m 接受。29.9999990003 m 段长拒绝，名义 30 m/上侧接受。同一 40 s、字节完全相同的重复输入，原 manager 接受两次；源代码没有该层去重，迁入也不虚构去重。首批边界标签未真正跨 500 m 的不足已由 v2 补齐，旧证据保留。

## 全长固定输入回放

计划覆盖 14 E0 + 14 E4，分别为每组六/十个 C++ 核心。四个 Python 业务模块另以定点向量和共同调度闭环验证，不宣称已做其每格 R0 全长回放。全部 28 格均完成本地最终库检查，并绑定原 trace→R1 自验→向量→最终库的哈希链。每项比较包含全回调计数、参数一致性、输出和内部状态、向量 SHA256、原周期及比较器 SHA256。全长 E4 包括真实环境核心，不是仅向船体播放外力。

| Case | 本地结果 | 完整 callbacks | outputs | 发布 fields | 证据 |
|---|---|---:|---:|---:|---|
| R01-E0 | True | 94971 | 61104 | 1835196 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R01-E0/comparison.json) |
| R01-E4 | True | 287795 | 127838 | 2393898 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R01-E4/comparison.json) |
| R02-minus-E0 | True | 442525 | 283223 | 8549502 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R02-minus-E0/comparison.json) |
| R02-minus-E4 | True | 1236863 | 548030 | 10286423 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R02-minus-E4/comparison.json) |
| R02-plus-E0 | True | 442501 | 283200 | 8549139 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R02-plus-E0/comparison.json) |
| R02-plus-E4 | True | 1236510 | 547892 | 10283886 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R02-plus-E4/comparison.json) |
| R03-minus-E0 | True | 441536 | 282820 | 8530073 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R03-minus-E0/comparison.json) |
| R03-minus-E4 | True | 1234457 | 547161 | 10266130 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R03-minus-E4/comparison.json) |
| R03-plus-E0 | True | 442531 | 283360 | 8549502 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R03-plus-E0/comparison.json) |
| R03-plus-E4 | True | 1237035 | 548077 | 10287225 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R03-plus-E4/comparison.json) |
| R04-E0 | True | 1453269 | 930070 | 28076295 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R04-E0/comparison.json) |
| R04-E4 | True | 4060848 | 1799235 | 33772141 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R04-E4/comparison.json) |
| R05-E0 | True | 509850 | 326559 | 9850580 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R05-E0/comparison.json) |
| R05-E4 | True | 1422823 | 630617 | 11834235 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R05-E4/comparison.json) |
| R06-E0 | True | 509867 | 326494 | 9850674 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R06-E0/comparison.json) |
| R06-E4 | True | 1425619 | 632039 | 11856156 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R06-E4/comparison.json) |
| R07-E0 | True | 888995 | 569455 | 17175940 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R07-E0/comparison.json) |
| R07-E4 | True | 2484076 | 1100764 | 20658205 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R07-E4/comparison.json) |
| R08-E0 | True | 698706 | 447617 | 13499574 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R08-E0/comparison.json) |
| R08-E4 | True | 1950409 | 864647 | 16221686 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R08-E4/comparison.json) |
| R09-E0 | True | 968451 | 620448 | 18710732 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R09-E0/comparison.json) |
| R09-E4 | True | 2705372 | 1199403 | 22499783 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R09-E4/comparison.json) |
| R10-E0 | True | 413416 | 264496 | 7987280 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R10-E0/comparison.json) |
| R10-E4 | True | 1155697 | 511262 | 9610675 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R10-E4/comparison.json) |
| R11-E0 | True | 2208362 | 1413132 | 42663549 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R11-E0/comparison.json) |
| R11-E4 | True | 6174146 | 2735544 | 51345395 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R11-E4/comparison.json) |
| R12-E0 | True | 375167 | 240138 | 7248063 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R12-E0/comparison.json) |
| R12-E4 | True | 1045317 | 463409 | 8693655 | [比较](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/full-vector-validation-01/R12-E4/comparison.json) |

发布字段各单位的最大误差（未将不同物理量揉成总分）：

| 单位 | 最大误差 | 所在 case/module |
|---|---:|---|
| m | 0 | R01-E0 / ship_dynamics_node |
| quaternion | 0 | R01-E0 / ship_dynamics_node |
| exact | 0 | R01-E0 / ship_dynamics_node |
| m/s | 1.7763568394e-15 | R01-E4 / current_engine_node |
| rad/s | 0 | R01-E0 / ship_dynamics_node |
| deg | 5.68434188608e-14 | R01-E4 / current_engine_node |
| N | 1.41881173477e-10 | R01-E4 / current_engine_node |
| N.m | 5.55883161724e-09 | R11-E4 / wave_engine_node |
| rad | 0 | R01-E0 / ship_guidance_node |
| 1 | 0 | R01-E0 / thrust_allocation_node |
| kN/rad | 0 | R01-E0 / thrust_allocation_node |
| kN | 0 | R01-E0 / thrust_allocation_node |
| kN.m | 0 | R01-E0 / thrust_allocation_node |
| 1 (six-decimal display) | 0 | R01-E0 / thrust_allocation_node |
| geographic degrees | 0 | R01-E0 / coordinate_transform_node |
| deg/s | 0 | R01-E0 / coordinate_transform_node |
| m^2/s^2 | 0 | R01-E4 / current_engine_node |
| deg^2 | 0 | R01-E4 / current_engine_node |
| s | 0 | R01-E4 / current_engine_node |

原 trace、R1、向量及最终库的逐模块哈希链见 [来源索引](evidence/original-gnc-20260910/validation-chain-index.json)。

最终结果：28/28，通过 224 次模块回放、37,547,114 次 callback、18,588,034 个发布输出及 421,085,592 个发布字段；内部状态逐字段门另行检查。
R11-E4 在同一原输入上按六核心、风、流、浪、聚合器五个分区执行。最终汇总要求十模块无缺失或重复、每个模块回调完整、向量 SHA 与原最终 manifest 一致，库和比较器身份一致；分区原报告保留。这仍是逐模块固定输入验证，不是一次自主闭环。

流式导出逐 callback 对齐原状态 ordinal；只有所有模块和状态完整后才写 manifest，验证向量压缩 SHA。已与旧格式全部 43 个边界调用、完整 32,282 个 wind 调用及 header 严格相等；缺末状态负例必须拒绝且不生成 manifest。压缩归档逐字节 SHA 往返验证，损坏旧 gzip 单独保留。早期磁盘满、180 s operational timeout 和日志时钟错位保留为失败尝试；超时改为 600 s 不改变算法或比较门。

为降低全长环境状态检查的开销，仅优化比较器元数据：FieldRule 的输出字典直接构造；字段名/固定单位规则作有界缓存。没有缓存状态值、跳过数值比较或改变门槛。300 份真实 wind 报告、198 份跨模块夹具报告及边界/负例与旧实现完整结果一致；两项微基准分别约 1.8×、2.0×。旧比较器源码按 SHA 归档，运行中进程保留其已加载版本，各例报告记录实际启动时比较器 SHA；新启动例使用新元数据实现。

## 同调度自主闭环

该层双方共用显式 FIFO/周期调度，但原端执行独立原 C++ ROS 类及原 Python ROS 类，运行 maps 检查未加载嵌入库。共用调度意味着可比较算法累计漂移，不证明 ROS executor 实时行为等价。预先门：位置最大 0.10 m、速度 0.01 m/s、艏向 0.05°，导航时点/导引段序列/DP/路线模式一致。

- R05-E0：1454 s，72,700 导航帧位置/艏向/速度全部零差；382,287 个完整发布输出通过。
- R06-E4：1454 s，最大位置差 0.001881 m，RMSE 0.000319 m，P95 0.000919 m，末差 0.001715 m；预先全部闭环门通过。

R06-E4 自主输出不是逐位相等：565 s 被动环境 JSON 力出现约 4e−13 N 差；物理字段严格阈值比较在 1266.3 s 约 0.03094 N 差。该观测保留，不能把自主闭环的累计门冒充严格同输入逐步通过。R06-E4 双方末距约 33.22 m，联合 15 m/0.3 m/s 观测时长 0；保真通过不代表原末端控制达标。

[R05 全输出](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/glibc-v8-r05-full-coupled-comparison.json)；[R06-E4 闭环](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/common-schedule-navigation-v8/R06-E4/comparison/comparison.json)；[R06-E4 严格物理输出差异](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/glibc-v8-r06-e4-physical-comparison.json)。
## 自由闭环、步长、随机种子

原生 R0 与嵌入版全 70 格完成，两者异步自主轨迹差显著，不能通过固定输入门直接作归因。最大位置差 R09-E0 1430.292 m、R08-E0 1276.429 m、R08-E4 965.265 m；原自身重复性也有数百米差。全部原始观测见[原版报告](2026-09-10-original-gnc-source-runtime-report.md)。

R03-plus-E0 船体 50 Hz→100 Hz 敏感性：63,100 共同样本，最大位置差 2.793 m，艏向差 0.613°，速度差 0.220 m/s。该试验双方均为嵌入原算法，改变的是步长，不能称原版与迁入等价门失败，也不能据此改默认原 50 Hz。[JSON](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/sensitivity-analysis/comparison.json) · [图](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/sensitivity-analysis/comparison.png)。
R06-E4 追加固定 seed 20240619/20240620/20240621：输入在运行前另存，不覆盖 70 格；仅改变原流/浪 seed。原 `random_seed_enable=false` 表示使用确定 seed，true 才调用 random_device。原/嵌入双方独立运行。已完成 3/3；全部已完成组通过：True。

| Seed | 位置最大差 mm | 位置 RMSE mm | 速度最大差 m/s | 艏向最大差 ° | 闭环门 | 证据 |
|---|---:|---:|---:|---:|---|---|
| 20240619 | 1.676548 | 0.328974 | 3.35379226853e-05 | 0.000902675789061 | True | [JSON](evidence/original-gnc-20260910/seeds/R06-E4-seed20240619.json) · [图](evidence/original-gnc-20260910/seeds/R06-E4-seed20240619.png) |
| 20240620 | 1.680593 | 0.361512 | 3.18371246067e-05 | 0.000933713255232 | True | [JSON](evidence/original-gnc-20260910/seeds/R06-E4-seed20240620.json) · [图](evidence/original-gnc-20260910/seeds/R06-E4-seed20240620.png) |
| 20240621 | 1.933291 | 0.411404 | 3.43188373482e-05 | 0.00104024384784 | True | [JSON](evidence/original-gnc-20260910/seeds/R06-E4-seed20240621.json) · [图](evidence/original-gnc-20260910/seeds/R06-E4-seed20240621.png) |


## 验收界限

没有完成实船资格或 MASS-L3 系统验收。原生 ROS 自由闭环大差仍属于已观察限制，不能全部归结为数学库；同输入及两组共同调度证明的范围必须限定。产品 24 格 0 个同时任务完成与硬安全通过，见[避碰集成报告](2026-09-10-original-gnc-integration-report.md)。

原 backend 部署可复现方法见 [README](../../cpp/original_gnc/README.md)。逐回调复验示例：

```sh
cd /Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration
PYTHONPATH=. /Users/marine/Code/Colav-Simulator/.venv/bin/python \
  tools/original_gnc/validate_native_vectors.py \
  --build build/original_gnc-glibc-v8 \
  --source /Users/marine/Code/external_sources/L4-5_source_only_20260824_v2 \
  --vectors tests/fixtures/original_gnc/reference_route_boundary_vectors_v2 \
  --output build/original-gnc-boundary-recheck
```
