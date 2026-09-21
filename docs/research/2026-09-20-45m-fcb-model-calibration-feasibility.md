# 45 m FCB 船舶模型离线校准与在线适应可行性

日期：2026-09-20  
对象：45 m hybrid fast crew boat（FCB），Colav-Simulator 与当前 GNC 源码。  
范围：实船数据如何校准/验证船体操纵模型、推进器/动力链、舵机、推力分配与控制模型；评估在线识别/训练证据。  
证据规则：设计规格、估算配置、缩尺试验、仿真、实船试验、在线实船预测分别标记；不能互相替代。

## 结论

1. **离线校参可行，现有四份设计文件只能提供初值和约束，不能证明当前仿真参数已代表实船。** 文件中没有本船海试时序、轴扭矩、船后实测推力、舵角反馈或运动传感器记录。规格书写的是拟执行的验船/海试项目，不是已完成的试验报告。
2. **在线适应的研究可行性已有实船数据证据，但船型与证据边界很窄。** 11 m 双水喷 USV 已用实测航行数据做滑窗在线参数辨识和短时运动预测；大型高速三体客船研究则支持先以独立海试操纵验证灰箱模型。未找到证明 45 m、三机三固定桨、双 PTO/PTI 混动 FCB 已安全地在线修改水动力、动力链、分配器或控制器并投入自动控制的证据。
3. **本船建议顺序：** 先补足遥测和受控海试 → 离线辨识推进/执行器 → 用实际执行反馈校准 3/4-DOF 船体模型 → 按独立航次/工况验收 → 再在影子模式更新少量可辨识参数或预测残差。在线模型先不获得控制命令权限。

## 1. 设计资料给出的本船边界

| 项目 | 资料给出的内容 | 对建模的含义与证据等级 |
|---|---|---|
| 船体 | LOA 45 m、Lpp 约 44.1 m、型宽 8 m；设计吃水 1.55 m，最大吃水 2.00 m。规格书载近似 DWT 100 t；Data Sheet 的 25 kn 性能点另标 30 t DWT。 | 尺寸和设计工况可做初始先验。100 t DWT、30 t DWT、排水量不是同一量；必须记录每次实船试验的排水量、吃水、纵倾、载荷和燃油/水舱状态。来源：[技术规格 REV T，第 1–2 页](</Users/marine/Desktop/Desktop/45M FCB Doc/MSQ-00725-RP-2 PRELIMINARY TECHNICAL SPECIFICATION REV T.pdf>)；[Data Sheet](</Users/marine/Desktop/Desktop/45M FCB Doc/45M Fast Crew Boat Data Sheet - Octagen.pdf>)。 |
| 速度与环境 | 规格书给最低服务速度 18 kn @ 85% MCR（summer load line）；Data Sheet 给约 25 kn @ 30 t DWT、100% MCR。规格书环境包括海区 A3，最小生存海况 Hs 约 3 m。 | 18 kn、25 kn、满载和轻载都属于不同模型适用点。不能把某一个配载下的定常阻力曲线泛化到所有航速/装载。来源同上。 |
| 主机、齿轮箱和混动 | 3 台 Cummins 约 1007 kW / 1350 hp @ 1900 rpm；传动比约 3.048:1。两舷 PTO/PTI 齿轮箱各带电机，规格书列 PTI 150 kW、PTO 功率随主机转速变化；中间机/齿轮箱也有不同配置。 | 发动机转速不是螺旋桨轴转速；PTI/PTO、柴油单独、ZE 等模式需要各自记录和映射。还缺本机序列号对应的扭矩/功率包络、齿轮箱效率/限值、轴系惯量、模式切换瞬态和实测反馈。来源：[规格书，第 10–12 页](</Users/marine/Desktop/Desktop/45M FCB Doc/MSQ-00725-RP-2 PRELIMINARY TECHNICAL SPECIFICATION REV T.pdf>)；[K38 主机技术协议](</Users/marine/Desktop/Desktop/45M FCB Doc/K38主机技术协议(1007kW) （no silencer）.docx>)。 |
| 推进器与舵 | 规格书规定 3 根轴、3 只固定螺距桨（中桨与边桨规格不同），2 只桨后舵；Bow thruster 规格写 2 × 0.9 tf。Data Sheet 写 2 × 10 kN。 | 这是三主推、两舵的异构布局；舵流场、每根轴推力、差推力偏航效应要分开记录。0.9 tf 约 8.8 kN，与 Data Sheet 10 kN 接近，但不等于 GNC 中 20 kN 的数值已获合同资料支持。 |
| 现有桨曲线 | 侧桨/中桨分别列 0、2…14 kn，单桨 300–1100 kW 的主机吸收功率、船后有效推力、主机 rpm。文件定义 P 已考虑齿轮箱/轴系损失；T 已考虑伴流、推力减额、相对旋转效率等船体影响。 | **文件未说明这条曲线来自实船测量、模型试验还是计算；现阶段不能把它视作经实船海试验证。** 只有前进象限，航速范围止于 14 kn；无倒车、制动、低于 300 kW、舵角/转向影响或波浪工况。曲线适用域以外不要外推、镜像倒推或再次乘船体减额。来源：[螺旋桨推力曲线.doc](</Users/marine/Desktop/Desktop/45M FCB Doc/45m HYBRID FAST CREW BOAT 螺旋桨推力曲线.doc>)。 |
| 合同海试方案 | 规格书第 5 页写测量航速标距线：85%/100% MCR 各 4 个双向 runs；记录主机冷却水温压和 engine rpm。转向试验记录回转直径/时间、舵行程时间和 35° 反舵序列；停止/倒车试验记录换令、轴达到稳态、停车时间/距离、倒车稳态等。 | 这是计划/规范条目；没有给出已执行海试日志，也没有要求条目中逐轴采集轴扭矩、轴转速、舵角反馈、GNSS/IMU/波流或逐时控制输入。以目前文本，足以验若干性能点，不足以完整辨识底层模型。来源：[规格书，第 5–6 页](</Users/marine/Desktop/Desktop/45M FCB Doc/MSQ-00725-RP-2 PRELIMINARY TECHNICAL SPECIFICATION REV T.pdf>)。 |

### 曲线和额定值的待核实项

在曲线 P=1007 kW 点，0 kn 时侧/中桨列出的 engine rpm 约 1425/1447；14 kn 时约 1681/1694。主机协议额定点约 1007 kW @ 1900 rpm。若两处 P/N 指同一主机功率和转速口径，1007 kW @ 1425 rpm 会对应约 6.75 kN·m，超过 1007 kW @ 1900 rpm 的约 5.06 kN·m 额定扭矩；14 kn 点约 5.72 kN·m。**这是口径/发动机扭矩包络的核对项，不足以单独判定曲线错误。** 曲线 P 是否已换算为轴功率、N 是否主机转速，以及 MCR/短时 overload、齿轮箱和 PTO/PTI 约束需由船厂、主机/齿轮箱供方书面确认。

规格书所列最低 18 kn 服务速度高于推力曲线 14 kn 上限；Data Sheet 25 kn 性能点更远。该曲线可作本船低速/中速前进的先验或诊断源，**不能单独支撑 18–25 kn 的静态推进限幅或高航速 GNC 预测**。

## 2. 当前 GNC / Colav-Simulator 参数来源审计

快照：Colav-Simulator `311a2ed7f40c155f73b543b4a6b7ab23dee7d453`；GNC `0bbce06d7ad9ba8330d1d9934070f75c16ac2cf7`。仅读源码和现有配置，未修改 GNC/模拟器业务文件。

| 层 | 当前实现和参数来源 | 可信边界 |
|---|---|---|
| 原生 GNC Plant | [`ship_dynamics_node.cpp`](../../../GNC/src/simulation/ship_dynamics/src/ship_dynamics_node.cpp#L29) 声明通用默认参数，如质量 1.6e7 kg、Lpp 150 m、型宽 25 m、吃水 10 m；[`load_parameters()`](../../../GNC/src/simulation/ship_dynamics/src/ship_dynamics_node.cpp#L299) 再从 YAML 覆盖；[`initialize_mass_matrix()`](../../../GNC/src/simulation/ship_dynamics/src/ship_dynamics_node.cpp#L432) 组成 surge/sway/roll/yaw 4DOF 质量阵。 | 该节点属于 simulation 包，GNC [`ship_config.yaml`](../../../GNC/src/platform/ship_bringup/config/ship_config.yaml#L3) 也把 `operational_profile` 标为 `simulation`；这是仿真实现/配置审计，不证明船载控制栈实际加载或执行了此 Plant。若加载 FCB YAML，模型参数不是这些通用默认值；必须确认实际 launch/运行参数及 YAML 哈希。默认值本身不是本船数据。配置值也不因进入原生 GNC 就自动成为实船标定。 |
| 原生 GNC FCB 船体 | [`ship_config.yaml`](../../../GNC/src/platform/ship_bringup/config/ship_config.yaml#L347) 载 Lpp 44.1 m、B 8 m、吃水 2 m、质量 220,000 kg、Izz 27e6 kg·m²；X/Y/N added-mass 与水动力系数见同文件第 350–370 行。文件注释把若干项标为 restore/fix/C-level Mock；Izz 注释直接说明按 `m*(0.25*Lpp)^2` 从较大旧值修正。控制配置另标 `speed_drag_feedforward` 为 C-level Mock，并说明实船阶段需用 speed-power/RPM trials 重校。 | 质量/惯量的当前文件值可作为候选基线；部分水动力阻尼和速度前馈是工程修正/模拟先验，不是海试测量。用户提交文件未提供 220 t 实测排水量、实际重心/惯量或水动力报告；需向船厂补 Hydrostatics/轻船重量与 Inclining report。来源：[GNC YAML](../../../GNC/src/platform/ship_bringup/config/ship_config.yaml#L347)；[控制源](../../../GNC/src/gnc/ship_control/src/ship_control_node.cpp#L218)。 |
| GNC 执行器几何/限制 | GNC YAML 第 280–345 行含 3 个主推、2 个 Bow tunnel、2 个 rudder；主桨中心位置 x=-18.094 m、侧桨 y=±3 m，舵 x=-19.594 m/y=±3 m。第 755–835 行列主推 135 kN/台、800 kW/台、直径 1.8 m、效率因子，Bow thruster 20 kN/台，舵面积 3.5 m²、升力斜率 2.8/rad、舵速 0.1 rad/s 等。见 [`ship_config.yaml`](../../../GNC/src/platform/ship_bringup/config/ship_config.yaml#L280)。 | 主推 135 kN/台、800 kW/台和桨径/效率因子是当前配置的限值/计算参数，不是给定实船海试证明；135 kN/台高于所给稳态曲线在额定 1007 kW 时约 79–83 kN/台。Bow 20 kN/台也高于设计规格 0.9 tf 或 Data Sheet 10 kN。必须核对这些是优化器边界、峰值瞬时值还是旧配置；桨舵位置也需与 as-built 图纸核准。舵叶面积/升力斜率/洗流比例在给定文件中没有来源图纸或海试证据。 |
| 推力曲线进代码 | GNC 有 [`propeller_curve_45m_fcb.csv`](../../../GNC/src/gnc/thrust_allocation/config/propeller_curve_45m_fcb.csv)，内容与设计曲线表的前进曲线点对应。但 [`PropellerCurveMap`](../../../GNC/src/gnc/thrust_allocation/include/thrust_allocation/propeller_curve_map.hpp#L25) 和 [`publish_propeller_curve_shadow()`](../../../GNC/src/gnc/thrust_allocation/src/thrust_allocation_node.cpp#L1613) 把曲线用作 shadow diagnostics，输出 `affects_thruster_commands=false`；推力命令走另一套分配/限幅。 | 曲线“在仓库”不等于曲线已经驱动 Plant/执行器。当前主机功率限制还使用独立经验公式（ship config 的 max_power/eta/直径，见 [`thrust_allocation_node.cpp`](../../../GNC/src/gnc/thrust_allocation/src/thrust_allocation_node.cpp#L1469)），与逐速中/边桨表的静态映射不同。 |
| 执行器动态和舵模型 | 原生 Plant 接收 `/thruster/commands` 中的抽象推力/舵角并以力、力矩推进状态；见 [`collect_thruster_forces()`](../../../GNC/src/simulation/ship_dynamics/src/ship_dynamics_node.cpp#L984)。实现有推力变化率/角度限值，但命令不是由发动机 rpm/轴扭矩状态生成。桨盘直径 1.8 m、洗流比例 0.55、舵面积 3.5 m²、升力斜率/失速和入流范围来自配置或源码常数。Colav 的 [`FCB45ActuationParameters`](../../colav_simulator/modular_gnc/fcb45_actuation.py#L42) 明确称其为 design estimates/engineering assumptions。 | 实现包含了可运行的舵力与洗流近似，未包含本船主机转速/扭矩动态、齿轮箱换挡、轴系扭转、PTI/PTO 电机/电池动力学。螺旋桨曲线仍不在动力学积分主路径。实际执行器反馈采到以后，才能分离“指令→执行器”误差与“执行器力→船体响应”误差。 |
| 在线参数更新入口 | [`ship_control_node.cpp`](../../../GNC/src/gnc/ship_control/src/ship_control_node.cpp#L39) 注册 ROS 参数回调；代码注释说明可热更新 PID 增益和限幅。 | 这是人工/外部参数写入接口，不是由航行日志自动估计船体或执行器参数的训练器。在本次审计的 GNC/Colav FCB45 路径中未发现在线辨识并写回 Plant、推力曲线或舵模型的算法；应区分“运行时可改参数”和“在线模型适应”。 |
| Colav-Simulator 模块化 Plant | [`plant.py`](../../colav_simulator/modular_gnc/plant.py#L21) 提供 3DOF 广义力模型和 4DOF roll 变体；[`catalog.py`](../../colav_simulator/modular_gnc/catalog.py#L97) 明列 FCB45 参数来源为同事提取的 `ship_config.yaml`，`validated_for_vessel=false`；第 521–559 行列当前质量、added-mass、阻尼与 roll-restoring 参数。 | `fcb45_3dof_plant`/`fcb45_roll_4dof_plant` 是可替换的仿真 Plant preset，不等于独立海试证据。部分阻尼按 7.8 m/s 线性化/缩放，代码备注为偏差项；18 kn 服务点约 9.26 m/s，数据表性能点 25 kn 约 12.86 m/s，覆盖整个运行域需另外验证。|

### 需先闭合的实现差异

1. **排水量和装载口径**：当前 GNC/模块 Plant 使用 220 t 和 2 m 吃水；用户资料给设计吃水 1.55 m、最大 2.00 m、DWT 近似 100 t，且 25 kn Data Sheet 点另为 30 t DWT。DWT 不能代替 displacement；须取得船舶 hydrostatics、载荷/舱柜状态和实船吃水记录。
2. **推力上限**：当前主推 135 kN/台、Bow 20 kN/台，与船方表格可用静态数据不匹配或未说明条件。按侧/中桨表 `P=1007 kW`，0 kn 每桨有效推力约 82.5/79.4 kN；设计 Bow 为 0.9 tf/Data Sheet 10 kN，而 GNC 配成 20 kN。先确认是优化器保护限值还是有效推力物理值。
3. **稳态映射不等于控制响应**：设计桨曲线可提供 `T_eff(V,N)` 与 `P(V,N)` 初值，但 GNC 的 Plant 接收力/舵角命令，不从发动机转速状态生成推力；没有本船柴油机/齿轮箱/PTI-PTO 模式的完整动态模型。当前固定主推变化率 200 kN/s、舵速 0.1 rad/s 也是配置，不是厂家动态证明。
4. **符号与模型口径**：原生 GNC 的 mass matrix 以 `mass + added_mass` 组装，Colav 的 SNAME 参数写成负 added-mass 并由 `m - Ẋ` 组装；这可能是等价的符号约定，需对照完整 mass matrix，而不是逐字比参数符号。原生 GNC 是 4DOF，Colav 另有 3DOF/4DOF，状态/执行器接口也不同。

## 3. 一手研究证据：实船数据校参与在线更新

| 研究/标准 | 数据、模型和识别法 | 验证集/结果 | 可支持的结论与边界 |
|---|---|---|---|
| Yoon & Rhee (2003), [DOI 10.1016/S0029-8018(03)00106-9](https://doi.org/10.1016/S0029-8018(03)00106-9) | 采用 113,000 DWT tanker 实船试航；先以 EKF + modified Bryson–Frazier smoother 估计运动状态、水动力力/矩和流速方向，再用 ridge regression 拟合 Abkowitz 型导数；用 D-optimal/PRBS 思路研究激励输入。 | 报告算法以 113K tanker 真海试确认；论文指出标准回转/Z 字轨迹可能无法单独区分所有水动力导数，并说明变量共线和海流可观测性是关键。 | 支持用真实轨迹辨识/验证大船操纵模型，也支持先估测未知状态/流再拟合。不能从单次普通营运轨迹识别所有系数，更不是在线 GNC 自动改参部署。 |
| Suyama et al. (2024), [Ocean Engineering 298, 117323](https://doi.org/10.1016/j.oceaneng.2024.117323) · [作者预印本](https://arxiv.org/abs/2312.04224) | 83 m、Lpp=83 m container ship M.V. SUZAKU。对先前由水动力/缩尺 captive test/CFD 确定的 MMG 参数，以 CMA-ES 联合调整 12 个对模型力/矩有影响的参数；参数搜索限于先验邻域。实船状态/操纵输入为 time series。论文说明本轮并未把 hydrodynamic derivatives 纳入调参目标；忽略风流并只考虑前进。 | 4 个未参与参数调优的实船转向序列（舵角 -10°、+20°、-35°、+40°）验证；搜索范围最宽时出现调参集更好、测试集变差的过拟合，作者选择测试集表现更好的边界区间。 | 直接支持“以物理灰箱作骨架，再用实船操纵序列小范围校准”。不能解读为 12 个水动力导数均由实船识别，也不支持把船型/推进器系数转移到 FCB。 |
| Perez et al. (2007), [原始论文 PDF](https://fossen.biz/publications/2007%20Perez%20et%20al%20FAST.pdf) | 127 m、35 kn 高速客运 trimaran；4DOF 灰箱模型。两套实际 35 kn Z 字试航；roll/yaw/执行器在约 30 Hz、GPS 位置/航速约 1 Hz。以 20°/20° 数据调参，使用工程初值并加遗传算法。 | 10°/10° 转向序列不调参，留出验证。论文说明海况/疑似流会产生偏差；只靠 Z 字激励不足以识别较多参数。 | 这是更接近高速客船的实船证据，说明先验+海试拟合+不同操纵留出验证可行；它不是相同船型/三轴柴油固定桨/混动系统，也不是线上参数更新。 |
| Kandemir et al. (2025), [Applied Ocean Research DOI 10.1016/j.apor.2025.104825](https://doi.org/10.1016/j.apor.2025.104825) | 真实海况 Otter USV（小型 full-scale 平台），3DOF SINDy；4 条直线和 4 条圆周操纵，用 GNSS/IMU/导航状态与推进输入训练。比较一次/二次多项式与物理启发的 custom dictionary。 | 逐操纵 holdout 与按操纵分折的 k-fold；另用训练所未见操纵检查自由预测/测量校正频率。复杂二次多项式出现过拟合；横向激励不足时跨 manoeuvre 验证变差。较低的状态校正频率会累积误差。 | 支持用真实试验数据构造可解释低维模型，并按完整操纵而非随机采样点切分。小型 USV、少量航次、环境传感不足；不是 FCB 高速/混动或在线 GNC 参数部署。 |
| Dong et al. (2025), [Control Engineering Practice 164, 106508](https://doi.org/10.1016/j.conengprac.2025.106508) · [UCL 作者稿](https://discovery.ucl.ac.uk/id/eprint/10217283/) | 11 m × 3.2 m 双 water-jet USV，轻船约 8,000 kg，在三亚近海采实船 10 Hz 数据；输入含实际 water-jet motor/engine speed n 与 rudder δ，状态 u/v/heading，yaw rate 由 heading 差分。3DOF 明确参数模型，以在线 sparse LSSVM、滑动窗、增量/减量 kernel inverse、LOOCV 剪枝更新参数/预测器。 | 10°/-10° steering 1750 组样本用于 online identification；5/7 s 运动预测；在 10°/-10° 转向和 10°、5° turning 试验做不同工况预测。窗口大小 100–400 有精度/耗时取舍；论文报告一个窗口配置耗时约 1.9 s，未形成船载硬实时 deadline 证明。 | 这是“真实全尺寸试验数据+在线辨识/预测”存在的强证据；但对象只有 8 t 双水喷、3DOF，测试是预测/辨识，不是自动控制权限下改动 45 m FCB GNC。论文亦指出对参数显式可分离的模型更适用；复杂耦合隐式参数的适用性受限。UCL 页面提供作者稿，未提供可下载的原始航行数据集，难以独立复现实验。 |
| Chen et al. (2023), [Ocean Engineering DOI 10.1016/j.oceaneng.2023.114183](https://doi.org/10.1016/j.oceaneng.2023.114183) | 4DOF MMG-informed LS-SVM；用 175 m 级大集装箱船参数构造**仿真数据**，输入 rudder angle/propeller rpm；在合成波浪扰动下，错误越限后以滑动窗重建/更新预测模型。 | 离线和“在线”比较都属于作者设计的 simulation experiment；不是这艘大船的实测数据或船载在线更新。 | 适合证明“滑窗误差触发可使仿真预测适应波浪扰动”；不证明物理 MMG 参数被正确在线识别，更不证明真实 FCB 的船载安全性。 |
| Oh et al. (2021), [Applied Sciences 11(17), 8197](https://doi.org/10.3390/app11178197) | 多艘油轮及 twin-skeg LNG 船 speed trial 真实测量 propeller thrust、torque、转速；比较轴应变计和光学测量方法。 | 用实船测速/自航试验结果比对测量设备；作者指出光学测量零位设置对准确性显著。 | 说明实船识别推进器/船体效率不能只看 engine RPM 或 GNSS speed，应测并校准 shaft torque/RPM；测到 thrust 的成本/设备需另评估。本船尚无此类实测。 |

**online 的术语边界：** 上述研究中的在线方法主要是在实测操纵数据到来时更新状态预测器/低维水动力参数。现有证据没有证明它们会自动更新发动机 ECU、PTO/PTI 能量管理、推力分配器或操纵控制增益，也没有证明在线候选模型直接取代安全控制主链。

## 4. 本船可执行的离线校准方案

### 4.1 先冻结参数台账，不从闭环误差直接“全参数搜索”

每个参数需有名称/单位/符号约定/坐标系/证据等级/数据来源/适用工况/不确定度。分成：

| 参数组 | 优先来源 | 本船处理办法 |
|---|---|---|
| 刚体质量、CG、惯量、吃水/纵倾、几何 | 完工重量、hydrostatics、approved inclining report、每航次 draft readings | 尽量取计量/船厂批准数据，不用转向轨迹反向吸收质量或重心误差；按装载工况留版本。 |
| 柴油机/齿轮箱/电机 | Cummins 的本机 load/torque curve、调速器反馈、Reintjes ratio/efficiency/扭矩及 clutch/PTI/PTO 资料、Danfoss torque-speed map | 先测“设定→转速/扭矩/功率”的延迟、饱和、速率、换挡/切换行为；区分三台发动机及 PTI/PTO 模式。 |
| 三只主桨 | 用户曲线的 `T_eff(V,N)`/`P(V,N)` 作侧/中桨先验；海试 shaft rpm/torque/thrust 实测校正 | 每根轴各自记录；先确认 N 是 engine rpm 或 shaft rpm、P 是 engine/shaft power。曲线之外不外推；倒车需另测。 |
| 两只舵/转向机构 | 舵图纸、角度反馈、方向机/油泵规格和实测舵速/滞后；多航速的舵操纵试验 | 先识别舵命令→实际角度的机械响应，再辨识舵力/局部桨流。舵面积、升力斜率、失速角和 wash fraction 不从轨迹单独假定为真值。 |
| 船体 3DOF/4DOF 水动力 | 对水速度/姿态/角速度、actual rudder/thrust，环境与装载同步；稳定的 MMG/Abkowitz/Fossen 结构 | 先拟合少量可辨识导数，保留水动力结构；如 roll / high-speed wave load 任务重要，再单独校准横摇和环境项。 |
| 分配器/控制器 | 实际执行器推力/角度反馈、分配输入/输出、饱和与控制模式切换记录 | 推力/力矩可达域与 actuator geometry 先校准，PID/LOS gains 最后在已验证 Plant 上调；不让 controller 误差被错拟合成 hull damping。 |

### 4.2 补采实船试验数据

规格书计划中的航速、回转、反舵和 crash-stop 项应按 Class/Owner 批准继续执行；在既有项目上补足辨识用记录字段。ITTC speed/power trial procedure 将 GNSS track/SOG、shaft torque 或 shaft power、shaft RPM、rudder angle、GPS time、depth、heading、relative wind 和波况列为单次 run 的主要数据；轴功率从扭矩与转速计算，建议校准扭矩计并完成零位检查。[ITTC 7.5-04-01-01.1 Rev.08 (2024)](https://ittc.info/media/11972/75-04-01-011.pdf)

| 同步采集 | 最低字段 | 不采的后果 |
|---|---|---|
| 状态/时间 | GNSS/RTK position/SOG/COG、对水速度或 speed log、heading/roll、IMU 角速度/加速度、传感器原生时间戳/延迟/质量 | current、yaw/roll dynamics、定位滤波延迟与真实船体参数混淆。 |
| 三套主机/传动 | 各机命令及反馈 rpm/load/fuel rate、gear/clutch 状态、每根轴 RPM/torque/power、实际正倒车/换向时间 | 只有 bridge 命令而没有轴反馈时，不能分离发动机/齿轮箱迟滞与船体响应。 |
| 混动 | port/starboard PTO/PTI 状态、电机 RPM/torque/current/voltage、battery SOC、EMS power split 和告警 | PTI/PTO 与柴油模式被混成同一 actuator map，离线模型会拟合出错误的“水动力变化”。 |
| 舵与其他执行器 | 每舵命令和 angle feedback、油压/限位/故障、两侧 Bow thruster 命令与反馈、电流/推力数据（可获得时） | 不能辨识舵角滞后/饱和；把 actuator deadband 当作舵效或 hull derivative。 |
| 环境/装载 | 风速风向（含仪器位置）、波高/周期/方向或明确标未知、流向流速/水深、三舱 draft、trim、载客/载货、燃油/水舱、displacement | 环境力、浅水、载荷效应被写进 hull resistance/阻尼，参数不可跨工况复用。 |
| 控制/运行模式 | manual/autopilot/DP/PTI/PTO/ZE、command source、setpoints、接管/饱和/安全限速事件，日志软件与参数版本 | 控制策略/限幅造成的行为会误归因为物理船模。 |

实船操纵试验优先在开阔、低流、足水深、低海况且载荷稳定的条件下做辨识基线；随后在安全许可的不同速度、舵角、载荷与混动模式重复验证。ITTC manoeuvring trials 建议全载/接近全载状态、平水和开放水域，并覆盖 course keeping、turning、zig-zag、stopping 等能力；实际 FCB 试验仍应由 BV/船东/船长批准，不把该通用建议当成本船法定验收标准。[ITTC 7.5-04-02-01 Rev.04 (2024)](https://ittc.info/media/11976/75-04-02-01.pdf)

采集内还需受控激励。除合同的 turns/zigzag/stopping 以外，在船长/船级社批准的试验窗口使用小幅多速率舵令、纵向 RPM ramp、左右轴差动和可安全执行的双向试验；按 Yoon-Rhee 的 D-optimal / PRBS 思想布置频率/幅值，增强参数可辨识性。Perez 的高速客船研究警告：Z 字试验不是为系统辨识而设计，单靠它不足以辨识大量系数。输入范围须落在既有船舶运行与 class 约束内，不为激励覆盖危险操纵。

### 4.3 拟合顺序和验收

1. **运行时钟/传感器/坐标先校准**：统一 GPS time、NED/body 坐标、heading/rate 符号，估计传感器时延/滤波；核验实际舵角/轴转速反馈和命令是一一对应且未错位。
2. **先静态几何/刚体和执行器，再船体导数**：确定排水量/CG/Izz；辨识舵机/发动机/齿轮箱响应；用已有推进表先校正前进中/边桨 map，随后测量高速与倒车域；最后拟合 hull added mass/damping/cross-flow/propeller-rudder interaction。环境载荷单独输入/估计，不和 hull damping 一起不受限搜索。
3. **灰箱优先，限制先验邻域**：对 MMG/Abkowitz/Fossen 结构保留物理意义；选少量高可辨识参数，以 weighted prediction-error / least squares / CMA-ES 约束搜索。参数要检查正质量阵、阻尼耗散、推进器方向/功率/扭矩边界、舵角/舵速边界。Suyama 结果显示扩大搜索边界可在训练数据上更好、留出数据更差。
4. **分段而非随机样本切分**：按完整操纵段、航次、配载、推进模式、海况分 train/validation/test；例如一组 turns/zigzags 用于调参，另一方向/角度转向、停车工况、另一航次作 holdout。相邻时间样本随机拆分会泄露相似状态，低估泛化误差。
5. **看闭环相关多指标**：独立报告 (a) 一步/5 s/更长期 open-loop 自由推演误差，(b) 速度/RPM/shaft-power map 误差，(c) turning diameter/advance、Z 字 overshoot/响应时间，(d) stop time/distance 与 astern 转换，(e) 高速 roll/heading；同时报告每参数置信区间、相关性/不可辨识参数、训练域和环境。只靠轨迹拟合可能给出可预测但不唯一的“等效系数”，不能称为物理真值。

## 5. 在线适应：建议定义与安全边界

### 可行对象

| 在线更新对象 | 对 FCB 的可行性 | 建议 |
|---|---|---|
| 短时状态/轨迹预测器或校准后模型残差 | 高，已有全尺寸水喷 USV 真实数据滑窗实验；不是 FCB 直接证据 | 先做 shadow predictions，适用于仿真回放/规划预测；将 data-driven residual 限制为受验证域内的小修正。 |
| 少量可辨识的低维物理参数（如某速段的推力倍率、一级迟滞时间常数、selected Nomoto/maneuvering response） | 中，水喷 USV online parameter estimation 有真实海试数据证据；三机三桨/混动 FCB 需新试验 | 初始在线适配只开 1–3 个低维参数，冻结其他参数；只在数据质量合格、模态恒定、输入激励足够且在模型域内时更新。 |
| 全部 3/4DOF MMG 导数、发动机/齿轮箱/PTO/PTI/Bow/Rudder/控制器共同在线训练 | 低，且参数耦合和辨识不足 | 不做一次性联合在线更新。多子系统同时更新会让水动力、风浪流、传感器滤波和执行器延迟互相补偿，参数漂移无法归因。 |
| Controller/PID、thrust allocation 约束直接在线自改 | 极低，未见该 FCB 实船安全部署证明 | 仅在离线回放/仿真或影子版本中评估；运行控制器保持冻结与独立限幅/监督。 |

### 分阶段适应门槛

1. **离线数字回放**：固定历史真实传感器与实际舵/轴/发动机反馈，候选在线算法不能看到未来数据；核查其逐时估参误差、窗口延迟、每次更新耗时和长时间预测漂移。
2. **影子海试**：在线运行估计器但不改变操纵输出。记录每次参数候选、窗口数据质量、辨识协方差、运行模式和适用域；与冻结基线进行同一时刻预测对比。
3. **参数候选准入**：只接受满足先验物理边界、跨留出 maneuver/航次有收益、无安全指标退化、数据覆盖充分的候选。候选仍先发至数字孪生/回放，不自动改船上 controller 或 actuator commands。
4. **有限域启用**：若后续确需船载自适应，要先由船东、船长、GNC 与 BV/相关审批方定义可用工况、独立安全监督、故障/数据无效即冻结、旧版回退、版本记录和人工接管门槛。在线模型不得突破 engine/gearbox/PTO/PTI 和舵/船速已批准限制。

硬门控至少包括：时钟/传感器健康；独立反馈有效；无命令饱和/传感掉线/新控制模式；特征落在已训练 envelope；持续激励足以辨识当前更新参数；更新量不越物理边界；candidate 对多步预测/操纵安全指标没有退化。滑动窗越新不等于越有信息；重复直航、恒 RPM 不能辨识侧向/艏摇阻尼和舵效。

## 6. 本船结论和下一步所需资料

**离线校参可做。** 目前可用 45m 设计曲线和主机/机舱规格作为物理先验、代码配置作为“当前实现清单”；需先取得船舶重量与水动力资料，再把海试数据补到 shaft/engine/rudder/roll/sensors 层。实船上船后，优先按工况采集整条控制-执行-运动链；针对每次运行建立可追溯的 raw log 和参数版本，然后先识别推进/舵机，再识别 hull。

**在线学习有限可做。** 最现实目标为“经离线海试校准的物理模型 + 有界/慢速 residual correction 或少量可辨识参数 shadow-updates”，把它先用于预测/数字孪生回放。已有真实数据研究在 11 m 双水喷 USV 上证明在线模型/参数更新能跑；同一论文未证明 45m 固定桨柴油混动 FCB 的实际执行器链、受控控制器权限与安全验证。可行性不能外推成船上即时改参已安全。

### 向船厂/主机/齿轮箱/供方索取

- as-built GA、船体线型/hydrostatics、载荷工况 displacement/LCG/VCG/TCG、inclining report、实际 prop/rudder drawings（直径/螺距/叶数/旋向/桨径/面积/力臂）。
- 三台发动机各自额定/连续/瞬态扭矩-转速-负荷曲线、实际 ECU rpm/load feedback 说明、各 PTO/PTI gearbox 型号和 transmission/efficiency/torque map、两电机与电池包及 EMS mode map。
- 中桨/边桨完整 `V–shaft RPM–torque/power–thrust` 表，覆盖 0–25 kn、低负荷、MCR/环境降额、倒车/换向（安全可测范围）；曲线模型的水速定义、P/N 口径和系数/试验来源。
- 两套舵机的行程/舵角精度/延迟/最大 slew /限制/压力/失效状态；两 Bow tunnel 实际推力与工作限速曲线。
- 船上现有可用的 4–20 mA / CAN / Ethernet / PLC / PEMS 信号字典和取数权限，真实采样率、时钟源、标定证书、反馈到底是 command 还是 measured state。
- 船级社/Owner 批准的 speed/power、maneuvering、stopping/astern、PTI/PTO 和风险控制试验计划；海试将采集逐轴 torque/RPM、rudder actual、GNSS/IMU/环境/载荷的频率、计量精度、坐标系和日志格式。

## 7. 标准及监管边界

- ITTC full-scale speed/power trials 提供轴扭矩/RPM/GNSS/舵角/风浪/水深/heading 和传感器标定方法，可作为辨识数据采集/分析参考。[ITTC 7.5-04-01-01.1 Rev.08 (2024)](https://ittc.info/media/11972/75-04-01-011.pdf)。
- ITTC full-scale manoeuvring trials 提供操纵试验项目和环境/装载建议，目的是确定对舵和发动机动作的响应。[ITTC 7.5-04-02-01 Rev.04 (2024)](https://ittc.info/media/11976/75-04-02-01.pdf)。
- [ISO 15016:2025](https://www.iso.org/standard/82080.html) 的 scope 是 Lpp 50–500 m displacement ships；本船 Lpp 约 44.1 m，**不在该标准明列长度范围**，可参考数据项/分析方法但不能宣称按其条文直接覆盖本船。
- [IMO MSC.137(76)](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.137%2876%29.pdf) 第 3.1 段将标准适用对象列为船长不小于 100 m 的船，以及不论长度的化学品船和气体运输船；本船 Lpp 约 44.1 m、资料标注为 crew transfer vessel，不属于列明的一般 100 m 范围。第 3.4 段另规定该标准不应用于相关 Code 定义的高速船。当前资料未确认 HSC Code 适用性；具体验收条件仍须由 BV/旗国/Owner 确认，本文只把该标准作为方法参考，不把它当成本船合规判据。

## 8. 来源清单

### 用户提供的船舶设计资料

- [45m HYBRID FAST CREW BOAT 螺旋桨推力曲线.doc](</Users/marine/Desktop/Desktop/45M FCB Doc/45m HYBRID FAST CREW BOAT 螺旋桨推力曲线.doc>)
- [MSQ-00725-RP-2 PRELIMINARY TECHNICAL SPECIFICATION REV T.pdf](</Users/marine/Desktop/Desktop/45M FCB Doc/MSQ-00725-RP-2 PRELIMINARY TECHNICAL SPECIFICATION REV T.pdf>)
- [K38 主机技术协议 (1007 kW)](</Users/marine/Desktop/Desktop/45M FCB Doc/K38主机技术协议(1007kW) （no silencer）.docx>)
- [45M Fast Crew Boat Data Sheet - Octagen.pdf](</Users/marine/Desktop/Desktop/45M FCB Doc/45M Fast Crew Boat Data Sheet - Octagen.pdf>)

### 代码与原始规范/论文

- GNC `ship_config.yaml`, `ship_dynamics_node.cpp`, `ship_control_node.cpp`, `thrust_allocation_node.cpp`, `propeller_curve_map.hpp`，链接见第 2 节。
- Colav-Simulator `catalog.py`, `plant.py`, `fcb45_actuation.py`，链接见第 2 节。
- [Yoon & Rhee 2003](https://doi.org/10.1016/S0029-8018(03)00106-9)；[Suyama et al. 2024](https://doi.org/10.1016/j.oceaneng.2024.117323)；[Perez et al. 2007 high-speed trimaran](https://fossen.biz/publications/2007%20Perez%20et%20al%20FAST.pdf)。
- [Kandemir et al. 2025 SINDy](https://doi.org/10.1016/j.apor.2025.104825)；[Dong et al. 2025 online sparse LSSVM](https://doi.org/10.1016/j.conengprac.2025.106508) · [UCL author manuscript](https://discovery.ucl.ac.uk/id/eprint/10217283/)；[Chen et al. 2023 online LS-SVM, simulation](https://doi.org/10.1016/j.oceaneng.2023.114183)。
- [Oh et al. 2021 full-scale thrust/torque sensors](https://doi.org/10.3390/app11178197)；[ITTC speed/power trial](https://ittc.info/media/11972/75-04-01-011.pdf)；[ITTC manoeuvring trial](https://ittc.info/media/11976/75-04-02-01.pdf)；[ISO 15016:2025](https://www.iso.org/standard/82080.html)；[IMO MSC.137(76)](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.137%2876%29.pdf)。

---

本调研仅新增本文档。未修改 Colav-Simulator/GNC 业务文件，未运行代码或测试；结论是可行性和证据边界，不是实船参数验收或控制链投产批准。
