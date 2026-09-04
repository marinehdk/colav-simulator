# GNC 航向改向超调与返航震荡：文献与工业实践调研

日期：2026-09-04

背景：Colav-Simulator 45m FCB（Lpp 44.1m、220t、双舵各 3.5m²、舵速 0.1 rad/s、三主推各 135kN、双 20kN 侧推、服务航速约 8 m/s），modular GNC stack（marine_pid 广义力矩 + 3DOF/4DOF M-C-D plant）出现 ROT 不足、转向后难收敛、避碰返航 S 形震荡。已定位结构性根因：planner 航向指令无参考整形直进 PID、plant 曾为零阻尼合成参数、PID 微分通道 dt 失配。同事真机 ROS2 源码已有机制（Nomoto 航速增益调度、SMC sat 边界层、NDO(Chen&Fossen)、转艏力矩软地板、航速自适应力矩上限、航向指令限速器、ILOS 积分治理/转弯相位调度、蟹角补偿）作为内部对照，本文只查外部权威文献。内部实验结论（2-DOF D 通道降 XTE ~10% 但舵程 +46.5% 被否；单轴航速调度与调度倍率滤波被否）作为权衡基准。

所有 DOI 均经 Crossref/IEEE/Wiley 核验，未发现 DOI 的会议论文/讲义以 URL 记录。

---

## 一、航向参考整形（heading reference shaping / rate limiter / S 型参考滤波）

**结论**：权威共识是在 heading command 与 autopilot 之间插入带 **rate limiting + speed(acceleration) limiting 的三阶参考模型**（积分链 ψ_d, r_d, ṙ_d），把改向机动显式分成三段（ROT 加速段—恒 ROT 段—ROT 减速段），输出 S 型航向轨迹；这是 Fossen 教材 successive-loop-closure 航向自动驾驶仪的标准前置级，动机原文即"rate limiting element 使改向机动由三相组成、避免执行器饱和"。rate limit 值的匹配方法：用一阶 Nomoto 稳态关系 r_ss = K·δ 与 zigzag 试验辨识的 K/T 定 r_max（留饱和裕度），一阶滤波（无 rate limit）会把瞬态全部甩给 PID，二阶无速率限幅仍会阶跃加速度。对本项目：这是治"planner 直进 PID"超调与末端收敛困难的第一优先结构，且与同事真机已有的"航向指令限速器"互为印证。

**证据**：

1. Fossen, *Handbook of Marine Craft Hydrodynamics and Motion Control*, 2nd ed., Wiley 2021, §15.2 "Autopilot Design Using Successive Loop Closure"（15.2.2 Case Study: Heading Autopilot for Marine Craft，p.516 起）、§12.1.1 "Reference Models for Trajectory Generation"。DOI: [10.1002/9781119575016](https://doi.org/10.1002/9781119575016)；目录全文见 [Booktopia TOC](https://www.booktopia.com.au/handbook-of-marine-craft-hydrodynamics-and-motion-control-thor-i-fossen/book/9781119575054.html)。关键内容：参考模型生成 ψ_d、r_d、ṙ_d，含速率/加速度限幅，三相 S 型改向。映射：直接给出本项目 heading command 限速器的标准实现形态（三阶 + 双限幅），而非简单一阶滤波。
2. 同书 §15.2 章节公开节选（Scribd 影印本）：["Ch15 Motion Control Systems"](https://www.scribd.com/document/874954128/Ch15-Motion-Control-Systems)，原文："The main motivation for using a rate limiting element in the reference model is that the course-changing maneuver will be described by 3 phases (positive turn rate acceleration / constant turn rate / negative turn rate acceleration)"。映射：证实 rate limiter 的作用机理就是消除"ROT 指令突变→PID 微分/积分瞬态→超调"链条。
3. Fossen 2005, "A Nonlinear Unified State-Space Model for Ship Maneuvering and Control in a Seaway", ENOC/Euromech。作者自托管全文：[fossen.biz PDF](https://www.fossen.biz/publications/2005%20Fossen%20Euromech.pdf)。原文（本文已抓全文核对）：autopilot 特性列表含"Reference feedforward using a dynamic model, ψd, rd, and ṙd, for course changing maneuvers. Course-keeping is obtained by using a constant reference signal"；给出 pole-placement 增益与参考模型方块图（pilot input → reference model → feedforward + PID）。映射：恒速直航（course keeping）与改向（course changing）共用同一参考模型，只是输入不同——本项目 planner 输出阶跃航向时应补的就是这一级。
4. 1st ed.（Wiley 2011）§12.2 "PID and acceleration feedback pole-placement algorithm"（p.374），目录 PDF：[Wiley front matter](https://onlinelibrary.wiley.com/doi/pdf/10.1002/9781119994138.fmatter)，DOI: [10.1002/9781119994138](https://doi.org/10.1002/9781119994138)。映射：旧版同样把参考模型+极点配置绑在一起讲，版本间结论稳定。
5. MSS（Marine Systems Simulator，Fossen/Perez 团队官方 Simulink 库）：[github.com/cybergalactic/MSS](https://github.com/cybergalactic/MSS)、概述论文 Perez, Smogeli, Fossen & Sørensen 2006, *Modeling, Identification and Control* 27(4)（作者页标注 DOI: [10.4173/mic.2006.4.4](https://doi.org/10.4173/mic.2006.4.4)）、配套 [FossenHandbook 代码库](https://github.com/cybergalactic/FossenHandbook)。映射：参考整形器有公开参考实现（SIMheading / 参考模型模块），可直接对照移植 marine_pid 前置级。
6. Nomoto, Taguchi, Honda, Hirano 1957, "On the steering qualities of ships", *International Shipbuilding Progress* 4(35)。DOI: [10.3233/isp-1957-43504](https://doi.org/10.3233/isp-1957-43504)。关键公式：一阶 Nomoto T ṙ + r = K δ，稳态 r_ss = K·δ_max 即船的固有 ROT 上限。映射：rate limiter 的 r_max 应满足 r_max ≤ K(u)·δ_max（留 10–20% 裕度防饱和），K 由 zigzag/回转辨识。
7.（锚点交叉验证法，推导）IMO MSC.137(76)（见第七节）初始转向指标：10° 舵角下 2.5L 内航向改变 10°——反推本项目 r_max 下限与 K 的可用校验线。映射：rate limit 与船实际能力匹配不当（过高→积分堆积超调，过低→ROT 不足）可用该指标二选一诊断。

---

## 二、2-DOF / r_ref 前馈 PID 航向 autopilot

**结论**：Fossen 体系推荐的 2-DOF 结构是"参考模型输出 (ψ_d, r_d, ṙ_d) + 模型前馈 τ_FF = (T/K)ṙ_d + (1/K)r_d（Nomoto 逆）+ 反馈 PID 只压误差"，前馈承担"该打的舵"，PID 只负责纠偏与抗扰，从而在不放大参考阶跃（无 derivative kick、不增加稳态舵程）的前提下加速跟踪。这与内部"裸 D 通道 (r_ref−r) 降 XTE 但舵程 +46.5%"实验的对偶关系很清楚：D 通道是在参考不可微时用高增益追 r_ref，代价转嫁为舵程与噪声；文献路线是先把 r_ref 整形成可微的 S 曲线再做前馈，代价转移到"需要 K/T 先验"。舵程代价的权衡证据：前馈本身在稳态不消耗额外舵（稳态 δ_ff = r_d/K 即物理需舵），额外舵程只出现在模型失配时。

**证据**：

1. Fossen 2005 Euromech（同上 URL，本文已核对原文公式 (187)）：τ_FF = (T/K)·ṙ_d + (1/K)·r_d；非线性 PID：τ_N = τ_FF + αr³ − Kp ψ̃ − Kd r̃ − Ki∫ψ̃；极点配置 Kp = T ωn²、Kd = 2ζωnT − 1、Ki = Kp/10（经验值）。映射：给出 marine_pid 的直接升级路径——加 τ_FF 项，同时 D 通道保持作用于测量误差（r_d − r），与内部 D 通道实验同一目标、不同（文献推荐）实现。
2. Fossen *Handbook* 2nd ed. §15.2.2（successive loop closure case study）、§15.3.4（pole-placement heading autopilot）、§16.1.5（LQR heading autopilot 对照）。DOI: [10.1002/9781119575016](https://doi.org/10.1002/9781119575016)。映射：教材把"参考模型 + 前馈 + 反馈"作为 case study 标准结构，LQR 版本只是反馈通道替代。
3. Fossen & Lekkas 2023, "An Adaptive Line-of-Sight (ALOS) Guidance Law for Path Following of Aircraft and Marine Craft", *IEEE TCST* 31。DOI: [10.1109/TCST.2023.3259819](https://doi.org/10.1109/TCST.2023.3259819)。关键内容：级联制导-控制增益明确按 "pole placement [Handbook, Algorithm 15.1]" 选取。映射：NTNU 系近期工程实现仍走极点配置 + 参考模型路线，属活跃实践而非过时教材内容。
4. Åström & Hägglund, *Advanced PID Control*, ISA 2006, ISBN 978-1-55617-942-6。关键内容：2-DOF PID（setpoint weighting、微分作用于测量避免 derivative kick）是通用控制文献对"参考突变引起超调"的标准处置；微分作用于参考会放大设定值噪声与阶跃。映射：解释内部 D 通道实验舵程 +46.5% 的机理（对 r_ref 高增益微分等效于抬高闭环带宽追参考），支持改用前馈实现同样收敛加速。
5. MSS 官方实现（URL 同第一节第 5 条）：heading autopilot demo 含参考模型 + 反馈组合。映射：可核对 τ_FF 离散实现细节（含 dt 处理），顺带对照本项目 PID 微分通道 dt 失配修复。

---

## 三、Nomoto 增益调度（航速自适应）

**结论**：舵效（舵法向力）∝ 进流速度平方（½ρA_R C_L U_R²），故 Nomoto 增益 K 随航速上升、时间常数 T 随航速缩短，这是水动力学第一性结论；固定增益 PID 在变速工况要么低速欠灵敏要么高速超调，1970 年代起（Källström 油船自适应 autopilot、Van Amerongen MRAS）就在实船上用自适应/调度解决，近年高速 ASV 文献进一步把 K、T 当"状态依赖参数"在线辨识。工业实践证据以自适应 autopilot 全尺寸试验与近年自动整定算法为主流。注意：文献支持的调度量是"舵效/操纵性随 u 变化"这一事实本身；本项目内部否决的是"单轴航速调度 + 调度倍率滤波"具体形态（横流末段 XTE 外扩），与文献不矛盾——文献同时要求叠加蟹角/流补偿（见第五节），否则变速+横流叠加时调度会帮倒忙。

**证据**：

1. Nomoto 1957（DOI 同前）：原始 K/T 定义基于线性化 M-C-D 系数，本身是 u 的函数。映射：K、T 非常数是源头文献立场。
2. Sutulo & Guedes Soares 2024, "Nomoto-type manoeuvring mathematical models and their applicability to simulation tasks", *Ocean Engineering* 308。DOI: [10.1016/j.oceaneng.2024.117639](https://doi.org/10.1016/j.oceaneng.2024.117639)。关键内容：系统梳理 Nomoto 方程无量纲化（K′、T′）与速度缩放约定及适用边界。映射：给出 K(u)、T(u) 重标定的规范公式来源（prime 记号体系）。
3. "State-dependent Nomoto modeling for high-speed autonomous surface vessels", *Ocean Engineering* 2026。DOI: [10.1016/j.oceaneng.2026.127396](https://doi.org/10.1016/j.oceaneng.2026.127396)。关键内容：把 K、T 作为状态依赖参数（随 u、漂角等变化）混合辨识框架。映射：45m FCB 服务航速 Fn≈0.38 属半滑行过渡区（见第七节），K 随 u 非线性更明显，单点 K/T 标定必然失配。
4. Källström, Åström, Thorell, Eriksson, Sten 1979, "Adaptive autopilots for tankers", *Automatica* 15。DOI: [10.1016/0005-1098(79)90042-6](https://doi.org/10.1016/0005-1098(79)90042-6)。关键内容：油船全尺寸自适应 autopilot 试验（STRS/SELENIA），速度/载况变化下在线重整定。映射：实船证据——变速变载工况固定增益不可用，调度/自适应是工业起点。
5. Van Amerongen 1984, "Adaptive steering of ships—A model reference approach", *Automatica* 20(1), 3–14。DOI: [10.1016/0005-1098(84)90060-8](https://doi.org/10.1016/0005-1098(84)90060-8)；作者自托管 PDF：[vanamerongen.org](https://afscheid.vanamerongen.org/publicaties/amerongen84.pdf)。更早谱系见 Van Amerongen & Udink ten Cate 1975, *Automatica*（DOI: [10.1016/0005-1098(75)90020-5](https://doi.org/10.1016/0005-1098(75)90020-5)）。关键内容：MRAS 航向自动驾驶，明确动机是船舶动态随速度/装载漂移；含实船试验。映射：同事真机 Nomoto 航速增益调度的文献同型物。
6. Kim, Kim, Jo, Yeo 2023, "Development of automatic gain-tuning algorithm for heading control using free-running test data", *Int. J. Naval Archit. Ocean Eng.*。DOI: [10.1016/j.ijnaoe.2023.100517](https://doi.org/10.1016/j.ijnaoe.2023.100517)。关键内容：用自航模（free-running）试验数据自动整定航向控制增益。映射：把"调度/整定"与"操纵性试验辨识"闭环起来的现代工业路线，可直接搬进本项目仿真在环流程。
7. Fossen *Handbook* 2nd ed. Ch. 9 "Control Forces and Moments"（舵/推进器力模型）与 Ch. 7 "Autopilot Models"（§7.2.1–7.2.3 Nomoto 一/二阶及非线性扩展）。DOI: [10.1002/9781119575016](https://doi.org/10.1002/9781119575016)。关键公式：舵升力 ∝ ½ρ A_R C_L(δ) U_R²，U_R 含推进器加速项。映射：舵效 ∝ u² 的教科书出处；本项目双舵+三主推的 U_R 应计入桨加速流。

---

## 四、NDO / ESO 干扰补偿在航向环的收益与风险

**结论**：NDO（Chen 2000 结构）对**缓变、有界、持续性**扰动（定常风/流、装载漂移）在航向环有实证收益（与自适应律组合后稳态误差与暂态均改善），同事真机 NDO(Chen&Fossen) 属主流可辩护方案；但文献同时明确其代价：观测器带宽受测量噪声限制，带宽过高把噪声/高频未建模动态注入舵令，模型惯性估计失配时补偿方向出错。开启判据建议：反馈+ILOS 积分仍残留**同号**稳态航向/横向偏差（持续外扰特征）时开；噪声水平高、扰动随机换向时不开，退回积分+前馈。ZOH/离散化失配会直接劣化观测器与微分通道，与本项目 dt 失配根因同源。

**证据**：

1. Chen, Ballance, Gawthrop, O'Reilly 2000, "A nonlinear disturbance observer for robotic manipulators", *IEEE Trans. Industrial Electronics* 47(4), 932–938。DOI: [10.1109/41.857974](https://doi.org/10.1109/41.857974)。关键内容：NDO 原始结构（比例增益型观测器 + 扰动动态模型），增益即带宽，讨论噪声折中。映射：真机 NDO(Chen&Fossen) 的结构出处；带宽选择规则（≤ 闭环带宽的若干分之一、受噪声上界约束）从这里来。
2. Chen, Yang, Guo, Li 2016, "Disturbance-Observer-Based Control and Related Methods—An Overview", *IEEE Trans. Industrial Electronics* 63(2), 1083–1095。DOI: [10.1109/TIE.2015.2478397](https://doi.org/10.1109/TIE.2015.2478397)。关键内容：四十年 DOBC 综述，明确适用域（扰动可估计、频带分离）与失效域（高频扰动、测量噪声、未建模柔性）。映射："何时值得开"的权威判据来源。
3. Liu et al. 2017, "Ship Adaptive Course Keeping Control With Nonlinear Disturbance Observer", *IEEE Access* 5。DOI: [10.1109/ACCESS.2017.2742001](https://doi.org/10.1109/ACCESS.2017.2742001)（Crossref 核验；PDF 见 [IEEE](https://ieeexplore.ieee.org/iel7/6287639/7859429/08013651.pdf)）。关键内容：船航向环 NDO+自适应，抑制未知有界时变外扰，仿真显示稳态/暂态改善。映射：与本场景最接近的正面证据（航向环、时变外扰）。
4. Liu et al. 2019, "Ship Heading Control with Speed Keeping via a Nonlinear Disturbance Observer", *Journal of Navigation* 72。DOI: [10.1017/S0373463318001078](https://doi.org/10.1017/S0373463318001078)。关键内容：NDO 同时处理航向+减速（伴生干扰）。映射：横流下"转向伴生速降"现象的补偿先例，对应本项目避碰大改向后动能损失。
5. "Active disturbance rejection control of ship course keeping based on nonlinear feedback and ZOH component", *Ocean Engineering* 2021。DOI: [10.1016/j.oceaneng.2021.109136](https://doi.org/10.1016/j.oceaneng.2021.109136)。关键内容：ESO/ADRC 航向保持，显式处理零阶保持（ZOH）离散化分量。映射：离散实现（dt、采样相位）对观测器/微分通道的影响有专门文献——与本项目 PID 微分通道 dt 失配同一问题类。
6. 有限时间 DO 自适应航向控制（2024，*Sensors*，开放全文）：[PMC11314828](https://pmc.ncbi.nlm.nih.gov/articles/PMC11314828/)。关键内容：有限时间收敛 DO + 输入饱和处理。映射：说明 NDO/ESO 在航向环仍是活跃改进方向，但均停留在仿真/小尺度验证，收益数量级文献间不可直接迁移。

---

## 五、ILOS 积分治理、弯道积分处理与 return-to-line 振荡

**结论**：ILOS 的积分项是为定常流/风补偿设计的（Fossen-Lekkas 谱系，USGES 稳定性证明依赖积分增益小、 lookahead 与船侧漂角匹配）；对"避碰后返航"的已知失效模式——积分在远离航线阶段持续堆积、回线后过冲并诱发 S 形振荡——近年文献给出明确治理手段：积分限幅/泄漏（wind-up mitigation）+ 转弯相位辅助（turning assist）/积分冻结或复位，2024 年已有把两者打包成统一 LOS 的 USV 论文。弯道跟踪的正解不是"弯道加大积分"而是曲率连续的路径参数化（单调三次 Hermite spline）+ 积分保持小增益。对本项目：同事真机"ILOS 积分治理/转弯相位调度"有直接文献支撑，且可进一步细化"离线距离超阈值→冻结/衰减积分"的触发条件。

**证据**：

1. Lekkas & Fossen 2014, "Integral LOS Path Following for Curved Paths Based on a Monotone Cubic Hermite Spline Parametrization", *IEEE TCST* 22(6), 2287–2301。DOI: [10.1109/TCST.2014.2306774](https://doi.org/10.1109/TCST.2014.2306774)。关键内容：曲率连续路径 + ILOS 补偿海流，避免分段直线航点处的参考跳变。映射：避碰返航接回原航线时的航向指令跳变，正是本项目"返航 S 形"的结构性来源之一；spline 参数化是路径侧解法。
2. Caharija et al. 2016, "Integral Line-of-Sight Guidance and Control of Underactuated Marine Vehicles: Theory, Simulations, and Experiments", *IEEE TCST* 24(4), 1623–1642。DOI: [10.1109/TCST.2015.2504838](https://doi.org/10.1109/TCST.2015.2504838)。关键内容：ILOS 最完整理论+实验分析（级联、USGES、积分增益与收敛/阻尼的权衡、实海流实验）。映射：积分增益过大→阻尼下降→回线振荡的机理出处；积分增益选择规则的原始依据。
3. Fossen & Lekkas 2017, "Direct and indirect adaptive integral line-of-sight path-following controllers for marine craft exposed to ocean currents", *Int. J. Adaptive Control and Signal Processing* 31(4)。DOI: [10.1002/acs.2550](https://doi.org/10.1002/acs.2550)。关键内容：自适应积分（直接/间接）替代固定积分增益，流强未知时自调。映射：恒定积分增益在"有流/无流"切换场景两头不讨好，自适应积分是中间路线。
4. "Unified line-of-sight: A guidance algorithm with integral wind-up mitigation and turning assist for USVs", *Ocean Engineering* 2024。DOI: [10.1016/j.oceaneng.2024.119615](https://doi.org/10.1016/j.oceaneng.2024.119615)。关键内容：标题即"积分抗饱和 + 转弯辅助"，针对 USV 大偏差回线与转弯场景治理 ILOS 积分。映射：与本项目症状（返航 XTE 大→积分堆积→S 形）与同事机制（积分治理/转弯相位调度）一一对应的最直接外部证据。
5. Kjerstad 2024, "Enhancing Line-of-Sight Guidance to Improve Path Following for Ships", *IFAC-PapersOnLine*（7th IFAC Conference on Control Estimation and Identification in Marine Applications? 以页面为准）。URL: [ScienceDirect PII S2405896324017786](https://www.sciencedirect.com/science/article/pii/S2405896324017786)。关键内容：指出 LOS/ILOS 在实船路径跟随中"文献不常讨论的缺陷"并给改进（全文未取得，引用级别=标题+摘要元数据）。映射：独立于 Fossen 谱系的工程视角缺陷清单，可作审查 checklist。
6. Fossen *Handbook* 2nd ed. §12.4.4 "Integral LOS"（course autopilot 版）、§12.5.1 "Crab Angle Compensation by Direct Measurements"、§12.5.2 "Integral LOS"（heading autopilot 版）、Appendix A（LOS 律 USGES 证明）。DOI: [10.1002/9781119575016](https://doi.org/10.1002/9781119575016)。关键内容：heading-autopilot 型 ILOS 需直接测流补偿蟹角，否则积分项会替船"硬扳"。映射：本项目已知横流末段问题——文献把"蟹角补偿"和"积分治理"绑定为组合件，单开任何一个都会在另一侧恶化（与内部否决"单轴航速调度"时观察到的末段 XTE 外扩一致）。
7. Fossen & Lekkas ALOS 2023（DOI 见第二节第 3 条）：自适应 lookahead + 积分的近期收敛版本。映射：若固定 lookahead 在 8m/s 与低速侧推工况间难以兼顾，ALOS 是文献上的下一档。

---

## 六、PID 整定方法论（极点配置 / 临界增益 / 优化寻优）

**结论**：船舶航向环的主流整定是**基于 Nomoto 模型的极点配置**（Fossen Algorithm 15.1：选 ωn、ζ 直接写 Kp/Kd，Ki≈Kp/10），ζ 常取 0.8–1（近临界阻尼）以压制超调——这与"改向无超调、末端快收敛"的目标一致；临界增益法（Ziegler-Nichols 类）面向 ~1/4 衰减比，天然欠阻尼，且要求现场逼近不稳定边界，不适合欠驱动船在仿真/实船上整定航向环，文献中船用基本只出现在历史综述里。多目标（XTE vs 舵程 vs 收敛时间）与约束（饱和、速率）下的参数选择，从 2000 年遗传算法（McGookin, Fossen 等）到近年贝叶斯优化+数字孪生都有成熟实践：低维（≤3-4 增益）网格+约束可行；中等维数、仿真昂贵时 BO 样本效率优势显著；安全约束场景用 SafeBO。对本项目：先极点配置给基线（可解释、可复算），再用仿真在环优化在"XTE/舵程"双目标上微调，与内部"舵程 +46.5% 不可接受"这类裁决配套多目标报告。

**证据**：

1. Fossen 2005 Euromech（同前，已核对原文）：Kp = T ωn²，Kd = 2ζωnT − 1，Ki = Kp/10；"controller gains can be found by pole placement, e.g. Fossen 2002"。映射：本项目 plant 换成非零阻尼 M-C-D 后，T、K 可从 3DOF 线性化或 zigzag 辨识，直接套公式得增益初值。
2. Fossen *Handbook* 2nd ed. §15.3 "PID Pole-Placement Algorithms"、Algorithm 15.1（p.523 起）、§15.3.4 heading case study。DOI: [10.1002/9781119575016](https://doi.org/10.1002/9781119575016)；ALOS 2023 论文实际引用该算法（"gains are chosen using pole placement [Algorithm 15.1]"，见 [IEEE 开放 PDF](https://ieeexplore.ieee.org/iel7/87/10292780/10087026.pdf)）。映射：算法有编号、有第三方工程引用，属可执行规格而非泛泛建议。
3. Åström & Hägglund, *Advanced PID Control*, ISA 2006（ISBN 978-1-55617-942-6）。关键内容：Z-N/临界增益法整定结果的阻尼水平（~1/4 衰减比）与 relay 自整定的适用条件；2-DOF 与微分滤波对噪声/参考阶跃的处理。映射：说明临界增益法为什么不适合直接给航向环用（欠阻尼 + 现场逼近失稳），以及 D 通道滤波/测量侧微分的正确姿势（对应 dt 失配修复后的验收标准）。
4. McGookin, Murray-Smith, Li, Fossen 2000, "Ship steering control system optimisation using genetic algorithms", *Control Engineering Practice* 8(4), 429–443。DOI: [10.1016/S0967-0661(99)00159-8](https://doi.org/10.1016/S0967-0661(99)00159-8)；作者页预印本：[fossen.biz PDF](https://www.fossen.biz/publications/2000%20McGookin%20et%20al%20CEP.pdf)。关键内容：GA 在仿真在环优化供应船转向控制器（含 SMC 参数）多目标代价函数，处理约束与多工况。映射：本项目"约束优化网格寻优 vs 进化算法"的直接同型先例；代价函数设计（加权 XTE/舵程/时间）可搬。
5. Marco, Hennig, Bohg, Schaal 2016, "Automatic LQR tuning based on Gaussian process global optimization", *ICRA*。DOI: [10.1109/ICRA.2016.7487144](https://doi.org/10.1109/ICRA.2016.7487144)。关键内容：GP-BO 用于控制器增益自动整定的样本效率与噪声鲁棒性基准。映射：仿真在环 BO 整定的通用方法学基线。
6. Delcaro, Gabrielli, Formentin 2026, "Bayesian optimization with executable digital twins: Fast controller tuning with multi-source information", *Control Engineering Practice*。DOI: [10.1016/j.conengprac.2026.107128](https://doi.org/10.1016/j.conengprac.2026.107128)。关键内容：数字孪生+多源信息的 BO 快速整定，虚拟/实测数据融合。映射：本项目"仿真在环整定、后续可接同事真机数据"的路线图文献。
7. Fu, Liu, Lan, Han, Shi, Zhang 2026, "A safe-by-design approach based on safe Bayesian optimization"（FOWT IPC 整定）, *Ocean*。DOI: [10.26599/OCEAN.2025.9470012](https://doi.org/10.26599/OCEAN.2025.9470012)；开放全文：[SciOpen](https://www.sciopen.com/article/10.26599/OCEAN.2025.9470012)。关键内容：SafeBO 零违反安全约束下比基线减载 20.3%/12.8%。映射：避碰场景"整定过程中不得出现危险机动"的安全约束整定范式（海域非海洋，方法同构，标注为跨域证据）。
8. Kim et al. 2023 IJNAOE（DOI 见第三节第 6 条）：自航试验数据→自动增益整定。映射：辨识与整定闭环的海洋工程实例，支撑"zigzag 辨识 K/T→极点配置→仿真在环校准"流水线。

---

## 七、45m 级快速船/FCB 操纵性指标锚点

**结论**：IMO MSC.137(76) 强制适用于 ≥100m 船（化学品/气体船不限长度），45m FCB 不在强制范围，且高速船无专属操纵性标准（NPS 综述明确"no specific maneuvering standards for high-speed crafts"）——但 MSC.137(76) 数值是全行业默认锚点，本项目可直接用作 plant+控制器联合验收线：Lpp=44.1m、V=8m/s → L/V=5.5s，落入最严档。注意本船 Fn = 8/√(9.81×44.1) ≈ 0.38 属半滑行过渡区，高速船此区间操纵性规律（回转圈随速度非线性变化、水喷射推进转向特性）与排水船不同，锚点校验时允许放宽解读但指标本身照测。最贴近的公开实船数据是 45m 水喷射双体船全尺寸操纵试验（Guedes Soares 等 1999）。

**证据（IMO 原文已逐条提取核对）**：

IMO Resolution MSC.137(76)《Standards for Ship Manoeuvrability》（2002-12-04 通过），全文 PDF 镜像：[doerry.org MSC.137(76).pdf](http://doerry.org/norbert/MarineElectricalPowerSystems/references/S_IMO_MSC.137-76/MSC.137(76).pdf)、[PUC Overheid 镜像](https://puc.overheid.nl/doc/PUC_1568_14?exp=1)。逐条标准（原文）：

1. 适用范围：`ships of all rudder and propulsion types, of 100 m in length and over, and chemical tankers and gas carriers regardless of the length`。试验条件：深水无限制、静环境、满载平吃水、稳定试速。映射：45m FCB 非强制对象；作为锚点使用时注意仿真吃水/载况设定与条件对齐。
2. 回转能力（35° 舵）：`advance ≤ 4.5 L`、`tactical diameter ≤ 5 L`。映射：本船 advance ≤ 198m、TD ≤ 220m；由 TD≤5L 反推稳态回转角速度 r_ss ≥ u/(2.5L) ≈ 8/110 ≈ 0.073 rad/s ≈ 4.2°/s（35° 舵）——这是诊断"ROT 不足"的量化线：plant 在 35° 舵下稳态 ROT 明显低于 4°/s 即回转能力不合格。
3. 初始转向能力（10° 舵）：航向改变 10° 前进距离 `≤ 2.5 L`。映射：≤110m，即 8m/s 下 ≤13.8s 内完成 10° 改向（平均 ≥0.73°/s）——小舵角快速性指标，直接约束 heading autopilot 整定后的小幅改向响应。
4. 10°/10° zigzag 超越角：第一超越角 `≤10°（L/V<10s）`、`≤20°（L/V≥30s）`、中间线性 `5+0.5·(L/V)` 度；第二超越角 `≤25°（L/V<10s）`、`≤40°（L/V≥30s）`、中间 `17.5+0.75·(L/V)` 度。映射：L/V=5.5s → 本船锚点为 1st ≤10°、2nd ≤25°；这正是"转向后收敛性"的标准度量——当前仿真若 1st overshoot 显著超 10°，即证实航向环阻尼不足（与超调症状同源）。
5. 20°/20° zigzag 第一超越角 `≤25°`。映射：大舵角改向场景（避碰转向近似）收敛锚点。
6. 停船 `track reach ≤15 L`（≤661m）。映射：可选校验项（本项目暂无倒停需求）。

**高速船/快船补充证据**：

7. Aslan 2015, *Maneuverability estimation of high-speed craft*, NPS 硕士论文。URI: [hdl.handle.net/10945/45808](https://hdl.handle.net/10945/45808)。关键内容（已提取原文）：`there are no specific maneuvering standards for high-speed crafts`；高速船被预期有更好操纵性故未设标准。映射：Q7 的"无专属标准"结论出处；同时给出高速船操纵性估算的特殊性。
8. Guedes Soares, Sutulo, Francisco, Santos, Moreira 1999, "Full-Scale Measurements of The Manoeuvring Capabilities of A Catamaran", *Proc. Int. Conf. Hydrodynamics of High Speed Craft*（RINA, London, 24–25 Nov 1999, paper 12）。无 DOI（1999 会议论文）；记录页：[ResearchGate 354096793](https://www.researchgate.net/publication/354096793_Full-Scale_Measurements_of_The_Manoeuvring_Capabilities_of_A_Catamaran)。关键内容：45m 水喷射推进快速双体船全尺寸操纵试验（回转/zigzag）。映射：与本 FCB 尺度、推进形态最接近的公开实船数据集，可作参数校验对照（水喷射 vs 本船舵推进，需注意差异）。
9. Kim et al. 2017, "Turning characteristics of waterjet propelled planing boat at semi-planing speeds", *Ocean Engineering* 145。DOI: [10.1016/j.oceaneng.2017.07.034](https://doi.org/10.1016/j.oceaneng.2017.07.034)。关键内容：半滑行速度段水喷射滑行艇回转特性（ Fn≈0.3-0.4 区间）。映射：本船 Fn≈0.38 同区间——回转半径/ROT 随速度的非单调行为提示航速调度不能只按 u² 单调外推。
10. Duman & Çakıcı 2022, "Turn and zigzag manoeuvres of Delft catamaran 372 using CFD-based system simulation method", *Ocean Engineering* 266。DOI: [10.1016/j.oceaneng.2022.112265](https://doi.org/10.1016/j.oceaneng.2022.112265)。映射：快速双体船 zigzag 数值基准流程（如何从 CFD/仿真取 K/T 与超越角）。
11. Mei et al. 2020, "Full-Scale Maneuvering Trials Correction and Motion Reconstruction for Modeling and Validation of a Twin-Screw Ship", *Sensors* 20(14), 3963。URL: [mdpi.com/1424-8220/20/14/3963](https://www.mdpi.com/1424-8220/20/14/3963)。关键内容：全尺寸操纵试验修正与按 IMO 指标验收流程。映射：双桨/双舵船试验数据处理与 IMO 指标对齐的标准做法（本船双舵三推）。
12.（背景常识，未单独取证）IMO MSC/Circ.1053 为 MSC.137(76) 的解释性 notes，给出试验实施细节。

---

## 对本项目的设计启示（按证据强度排序）

### 强证据必选（教科书/标准/高引一手文献直接支持）

1. **加三阶参考整形器（rate + accel 限幅，S 型）于 heading command 与 marine_pid 之间**——Fossen Handbook 2nd ed §15.2/§12.1.1 + 2005 Euromech 原文；这是对"planner 航向指令直进 PID"根因的标准解，同时天然消解 D 通道 derivative kick 与积分瞬态。r_max 匹配：r_max ≤ K(u)·δ_max（K 由 zigzag 辨识），下限用 IMO 初始转向/回转锚点校验（35° 舵稳态 ROT ≥4.2°/s、10° 舵 13.8s 内转 10°）。
2. **2-DOF 化：模型前馈 τ_FF = (T/K)ṙ_d + (1/K)r_d，D 通道保留在测量侧（r_d − r）**——Fossen 2005 eq.(187)；相对内部被否的"裸 D 通道"方案同目标、无稳态额外舵程代价（稳态 δ_ff 即物理需舵），前提是先用 1 把 r_ref 变光滑。
3. **极点配置整定替代手试/临界增益法**：Kp = T ωn²、Kd = 2ζωnT − 1、Ki ≈ Kp/10，ζ 取 0.8–1——Fossen Algorithm 15.1（§15.3），配 IMO 10/10 zigzag 1st overshoot ≤10°（L/V=5.5s 档）作验收门。
4. **ILOS 积分治理三件套：限幅/泄漏 + 离线距离触发冻结 + 转弯相位复位/降增益**——Caharija 2016（积分-阻尼权衡机理）+ Unified LOS 2024（wind-up mitigation + turning assist 同框）+ Lekkas & Fossen 2014（曲率连续路径减少指令跳变）；返航线接入用 spline 过渡。
5. **把 IMO MSC.137(76) 指标设为 plant+控制器联合回归测试**：TD ≤220m、advance ≤198m、10/10 1st ≤10°/2nd ≤25°、20/20 1st ≤25°——标准原文已核；ROT 不足与"转向后难收敛"分别由第 2、4 条指标量化诊断。

### 中证据候选（同行评议期刊支持，但形态需本场景适配）

6. **Nomoto 航速调度的规范化重做**：K、T 用 prime 体系按 u 重标定（Sutulo & Soares 2024），而非单轴倍率；必须与蟹角补偿/横流项联合启用（Fossen §12.5.1，文献把两者绑定为组合件）——否则重蹈内部"横流末段 XTE 外扩"覆辙；半滑行区（Fn≈0.38）K-u 关系非线性（Kim 2017、State-dependent Nomoto 2026），建议至少两点（8m/s 与低速侧推工况）辨识。
7. **NDO 按条件启用**：同号稳态残差>阈值且 ILOS 积分已到限幅时开；带宽受噪声上界约束（Chen 2000/2016）；离散实现必须先修 dt 失配（ZOH-ADRC 2021 为同类教训）。
8. **仿真在环多目标寻优（XTE/舵程/收敛时间，带饱和约束）**：GA（McGookin 2000，船域直接同型）或 BO（Marco 2016、Delcaro 2026；安全约束用 SafeBO——Fu 2026，跨域）；维度 ≤4 时网格扫描足够，先极点配置基线再局部寻优。

### 弱证据观望（机理有文献、收益量级未在本场景验证）

9. **自适应/ALOS lookahead**（Fossen&Lekkas 2017、ALOS 2023）：固定 lookahead 两速域难兼顾时再上。
10. **最优轨迹生成参考（§12.1.3）/高阶整形**：当前三阶 S 型够用，避免过度工程。
11. **HSC 专属操纵性标准**：不存在（Aslan 2015）；IMO 锚点放宽解读即可，等 IMO/船级社动态。
12. **SMC 边界层/超螺旋整定**（真机已有，Handbook 2nd §16.4 case study 支持）：整定仍走第 3/8 条流程，不单独引入新机制。

### 参考文献汇总（去重）

- Fossen, *Handbook of Marine Craft Hydrodynamics and Motion Control*, 2nd ed., Wiley 2021. DOI: 10.1002/9781119575016（1st ed. 2011: 10.1002/9781119994138）
- Fossen 2005, ENOC/Euromech 全文: https://www.fossen.biz/publications/2005%20Fossen%20Euromech.pdf
- Nomoto et al. 1957, ISP. DOI: 10.3233/isp-1957-43504
- Sutulo & Guedes Soares 2024, Ocean Eng. DOI: 10.1016/j.oceaneng.2024.117639
- State-dependent Nomoto 2026, Ocean Eng. DOI: 10.1016/j.oceaneng.2026.127396
- Källström et al. 1979, Automatica. DOI: 10.1016/0005-1098(79)90042-6
- Van Amerongen 1984, Automatica. DOI: 10.1016/0005-1098(84)90060-8（PDF: https://afscheid.vanamerongen.org/publicaties/amerongen84.pdf）
- Van Amerongen & Udink ten Cate 1975, Automatica. DOI: 10.1016/0005-1098(75)90020-5
- Kim et al. 2023, IJNAOE. DOI: 10.1016/j.ijnaoe.2023.100517
- Chen et al. 2000, IEEE TIE. DOI: 10.1109/41.857974
- Chen et al. 2016, IEEE TIE. DOI: 10.1109/TIE.2015.2478397
- Liu et al. 2017, IEEE Access. DOI: 10.1109/ACCESS.2017.2742001
- Liu et al. 2019, J. Navigation. DOI: 10.1017/S0373463318001078
- ZOH-ADRC 2021, Ocean Eng. DOI: 10.1016/j.oceaneng.2021.109136
- Finite-time DO 2024, Sensors. https://pmc.ncbi.nlm.nih.gov/articles/PMC11314828/
- Lekkas & Fossen 2014, IEEE TCST. DOI: 10.1109/TCST.2014.2306774
- Caharija et al. 2016, IEEE TCST. DOI: 10.1109/TCST.2015.2504838
- Fossen & Lekkas 2017, IJACSP. DOI: 10.1002/acs.2550
- Fossen & Lekkas ALOS 2023, IEEE TCST. DOI: 10.1109/TCST.2023.3259819
- Unified LOS 2024, Ocean Eng. DOI: 10.1016/j.oceaneng.2024.119615
- Kjerstad 2024, IFAC-PapersOnLine. https://www.sciencedirect.com/science/article/pii/S2405896324017786
- Åström & Hägglund, *Advanced PID Control*, ISA 2006. ISBN 978-1-55617-942-6
- McGookin et al. 2000, CEP. DOI: 10.1016/S0967-0661(99)00159-8（PDF: https://www.fossen.biz/publications/2000%20McGookin%20et%20al%20CEP.pdf）
- Marco et al. 2016, ICRA. DOI: 10.1109/ICRA.2016.7487144
- Delcaro et al. 2026, CEP. DOI: 10.1016/j.conengprac.2026.107128
- Fu et al. 2026, Ocean. DOI: 10.26599/OCEAN.2025.9470012
- IMO Res. MSC.137(76). http://doerry.org/norbert/MarineElectricalPowerSystems/references/S_IMO_MSC.137-76/MSC.137(76).pdf
- Aslan 2015, NPS thesis. https://hdl.handle.net/10945/45808
- Guedes Soares et al. 1999, RINA HSC. https://www.researchgate.net/publication/354096793
- Kim et al. 2017, Ocean Eng. DOI: 10.1016/j.oceaneng.2017.07.034
- Duman & Çakıcı 2022, Ocean Eng. DOI: 10.1016/j.oceaneng.2022.112265
- Mei et al. 2020, Sensors 20(14):3963. https://www.mdpi.com/1424-8220/20/14/3963
- MSS 工具箱: https://github.com/cybergalactic/MSS ；概述 DOI: 10.4173/mic.2006.4.4 ；FossenHandbook: https://github.com/cybergalactic/FossenHandbook
