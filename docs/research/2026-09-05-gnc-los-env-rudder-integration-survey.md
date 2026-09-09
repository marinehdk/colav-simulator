# GNC 栈集成设计调研：LOS、环境载荷与舵执行器

日期：2026-09-05
项目：Colav-Simulator，45 m FCB，`modular_gnc` 插件式 plant / guidance / controller / allocator / actuator dynamics / environment。

## 阅读边界与证据等级

- **[标准/教材]**：Fossen《Handbook of Marine Craft Hydrodynamics and Motion Control》2nd ed.（Wiley, 2021，DOI：[10.1002/9781119575016](https://doi.org/10.1002/9781119575016)）、IMO/ITTC/OCIMF/船级社正式文件。
- **[一手论文]**：Breivik、Fossen、Lekkas、Caharija 等论文原文或 DOI 元数据；若出版商正文不可公开抓取，只引用已核验的题名、摘要和 DOI，并明确不把未见到的方程写成“原文公式”。
- **[项目证据]**：本仓库当前实现。代码事实不是外部标准，单独标注。
- **[工程判断]**：针对本船尺寸、8 m/s 服务航速和静态最小二乘分配器的建议；不是行业强制要求。

> 重要限制：OCIMF MEG4 的风系数面向油轮；ITTC、DNV、ABS 的完整程序/规则正文受站点或 PDF 访问限制。本报告只把官方页面实际支持的内容作为规范性结论，不把油轮系数或船级社校核公式外推成 FCB 标准。需要认证或实船设计时，应锁定具体规则版本并由船级社复核。

---

## 一、LOS 导引家族

### 1.1 几何关系：pure pursuit、LOS、ILOS、ALOS

设当前航迹段切向角为 \(\alpha\)，带符号横向误差为 \(e\)，船舶对地航迹角为 \(\chi\)，前瞻距离为 \(\Delta>0\)。直线航段最常见的 LOS 参考为

\[
\chi_d = \alpha-\arctan\!\left(\frac{e}{\Delta}\right).
\]

它不是“把船头直接指向最近航点”，而是把参考点放在航迹前方 \(\Delta\) 处；因此相较于最近点追踪，LOS 对测量噪声和局部航线折角更平滑。Breivik、Fossen、Skjetne 将该类方法用于欠驱动船的路径跟踪；原始论文是 *Line-of-sight path following of underactuated marine craft*，IFAC Proceedings Volumes 36(21), 211–216, 2003，DOI：[10.1016/S1474-6670(17)37809-6](https://doi.org/10.1016/S1474-6670(17)37809-6)。该论文和 Fossen 教材的路径跟踪章节是 LOS 航海应用的主要一手来源。[标准/一手论文：Breivik, Fossen & Skjetne 2003；Fossen 2021，DOI 同上]

**Pure pursuit** 通常取几何视线方向

\[
\chi_d=\operatorname{atan2}(y_L-y,\,x_L-x),
\]

其中 \((x_L,y_L)\) 是目标点或前视点。它实现简单、适合点目标或短路径段，但 \(\Delta\) 对曲率和速度敏感，且没有显式的恒定流/风漂角估计。它是几何跟随策略，不等于针对欠驱动船证明过的 LOS/ILOS 闭环。[工程分类；具体船舶 LOS 谱系见 Breivik, Fossen & Skjetne 2003]

**ILOS（Integral LOS）** 在 LOS 中增加积分状态 \(z\)，典型写法为

\[
\dot z=e,
\qquad
\chi_d=\alpha-\arctan\!\left(\frac{e}{\Delta}+\kappa z\right),
\]

或等价地将 \(e+K_i z\) 放入分式分子。\(z\) 估计未建模的恒定漂移/侧滑，使反馈不必长期保持一个“硬扳”航向偏置。Caharija 等给出了欠驱动海洋航行器的理论、仿真和实海试验；论文题为 *Integral Line-of-Sight Guidance and Control of Underactuated Marine Vehicles: Theory, Simulations, and Experiments*，IEEE TCST 24(5), 1623–1642, 2016，DOI：[10.1109/TCST.2015.2504838](https://doi.org/10.1109/TCST.2015.2504838)。该工作的重要结论不是“积分越大越好”，而是积分增益、前瞻距离、船舶航向环阻尼和可实现的侧滑补偿需要共同满足有界性/收敛条件；积分增益过大可能降低闭环阻尼并引起回线过冲。[一手论文：Caharija et al. 2016]

**ALOS（Adaptive LOS）** 把漂角、漂移扰动或 LOS 参数作为待估计量，而不是仅依赖固定 \(K_i\)。相关谱系包括：

1. *Line-of-Sight Path Following for Dubins Paths With Adaptive Sideslip Compensation of Drift Forces*，Fossen、Pettersen、Galeazzi，IEEE TCST 23(2), 820–827, 2015，DOI：[10.1109/TCST.2014.2338354](https://doi.org/10.1109/TCST.2014.2338354)。题名和论文元数据确认其核心是**自适应漂角补偿**，不是固定蟹角。[一手论文]
2. *Direct and indirect adaptive integral line-of-sight path-following controllers for marine craft exposed to ocean currents*，Fossen、Lekkas，IJACSP 31(4), 445–463, 2017，DOI：[10.1002/acs.2550](https://doi.org/10.1002/acs.2550)。摘要明确区分：间接方法用观测器估计海流并补偿；直接方法用自适应 ILOS，给出收敛与参数有界性。[一手论文摘要]
3. *An Adaptive Line-of-Sight (ALOS) Guidance Law for Path Following of Aircraft and Marine Craft*，Fossen，IEEE TCST 31(6), 2887–2894, 2023，DOI：[10.1109/TCST.2023.3259819](https://doi.org/10.1109/TCST.2023.3259819)。该版本为 CC BY 4.0；其 DOI 元数据确认是 ALOS，但本次可用抓取未取得正文方程，因此不把某个具体观测器写成“2023 原文公式”。[一手论文]

工程上常见的自适应漂角接口可写成

\[
\chi_d=\alpha-\arctan\!\left(\frac{e}{\Delta}\right)-\hat\beta,
\qquad
\dot{\hat\beta}=\gamma_\beta\,\Phi(e,\Delta,U),
\]

其中 \(\Phi\) 必须与所选论文的误差坐标和船舶模型一致；文献中可见基于横向误差、速度和有界归一化因子的更新律。**不要把此抽象式直接当成 Fossen 2023 的可替代实现**：若项目要落地 ALOS，应先取得版本化全文，逐式复现符号、投影速度和投影误差，再写 parity test。[工程接口；论文逐式实现为必要前置]

### 1.2 收敛性与适用条件

- 纯 LOS 的收敛论证通常假设路径段光滑或分段处理、对地速度有正下界、航向环足够快且船能产生所需横向/艏向响应。对于强流、低速、急折线和执行器饱和，这些假设会失效。[Breivik, Fossen & Skjetne 2003；Fossen 2021]
- ILOS 通过积分状态消除定常漂移，但理论收敛依赖恒定/缓变扰动、有界积分状态、正的前瞻距离以及合适的小积分增益；Caharija 等的结果以级联制导—控制和 USGES/有界性分析为核心，不支持任意增大 \(K_i\)。[Caharija et al. 2016]
- 自适应 LOS 可减少对已知流场或固定漂角的依赖，但增加一个估计器状态和参数收敛条件；如果扰动快速时变、传感器噪声大或船舶速度接近零，参数估计可能漂移，不能自动替代外部流测量。[Fossen & Lekkas 2017；Fossen 2023]
- 曲线路径应优先使用曲率连续的路径参数化，而不是用大量折线把曲线近似出来。Lekkas & Fossen 的 *Integral LOS Path Following for Curved Paths Based on a Monotone Cubic Hermite Spline Parametrization*，IEEE TCST 22(6), 2287–2301, 2014，DOI：[10.1109/TCST.2014.2306774](https://doi.org/10.1109/TCST.2014.2306774)，专门处理单调三次 Hermite 样条与 ILOS 的组合。[一手论文]

### 1.3 前瞻距离 \(\Delta\)：来源、调度和边界

没有一个由 IMO、ITTC 或 Fossen 教材规定、适用于所有船型的固定 \(\Delta/L_{pp}\)。\(\Delta\) 是制导—控制带宽和曲率跟踪之间的工程调节量：较小会更积极但更易放大噪声、舵动作和折角冲击；较大会平滑、抗噪，但转弯切角和收敛距离变大。[Fossen 2021；Breivik, Fossen & Skjetne 2003]

常见工程形式是

\[
\Delta(U)=\operatorname{clip}(\Delta_0+k_U U,\Delta_{\min},\Delta_{\max}),
\]

或先按船长归一化：

\[
\frac{\Delta}{L_{pp}}=\operatorname{clip}(a+bU,\,a_{\min},a_{\max}).
\]

用户提出的 \(\Delta=L_{pp}(\Delta_{\min}+\gamma U)\) 只有在 \(\gamma\) 具有 \(s/m\) 单位、且 \(\Delta_{\min}\) 为无量纲时才量纲正确；它是**速度调度经验式**，不是可直接归因给某一篇 Fossen/Breivik 原文的统一标准。建议先做有界扫描，而不是把该式当定律。对本船可把服务航速的初始测试窗设为 \(0.8L_{pp}\)–\(1.5L_{pp}\)（约 35–66 m），低速时保留不小于约 \(0.5L_{pp}\) 的平滑下限；这是仿真验收窗，不是规范范围。当前固定 \(\Delta=50\,m\approx1.13L_{pp}\) 位于合理的首轮测试点。[工程判断；参数范围须用闭环回归确认]

曲率 \(\kappa_p\) 较大时还应满足几何可行性检查，例如 \(\Delta |\kappa_p|\) 不要长期远大于 1，否则前视点已经跨过弯道。该检查是几何启发式，不是船级社限值。[工程判断]

### 1.4 ILOS 积分边界：主流做法还是项目约束

若采用

\[
\chi_d=\alpha-\arctan\!\left(\frac{e}{\Delta}+\kappa z\right),
\]

并要求积分项单独造成的最大航向偏置不超过 \(\theta_{\max}\)，则直接得到

\[
|\kappa z|\le \tan\theta_{\max},
\qquad
z_{\max}=\frac{\tan\theta_{\max}}{|\kappa|},
\]

若实现把积分状态定义为 \(I=\Delta z\)，则

\[
I_{\max}=\frac{\Delta\tan\theta_{\max}}{|\kappa|}.
\]

这是一种**可解释的工程反算**，能把“积分限幅”映射为最大允许航向效应；但文献主流的稳定性处理是对积分状态/积分增益施加有界性与小增益条件，并没有一个跨船型、跨坐标定义的统一 \(I_{\max}\) 公式。必须先确认 \(I\) 是 \(\int e\,dt\)、\(\Delta z\)，还是已乘过速度/归一化因子的状态。[Caharija et al. 2016；Fossen 2021；工程推导]

建议同时使用三件套：

1. 对 \(z\) 或 \(I\) 做对称限幅；
2. 横向误差很大、路线刚切换或处于急转弯相位时冻结/泄漏积分；
3. 以实际航向偏置上限反算限值，并在记录中追踪“积分贡献角”。

2024 年 Tanakitkorn 等的 *Unified line-of-sight: A guidance algorithm with integral wind-up mitigation and turning assist for USVs*，*Ocean Engineering* 314, 119615，DOI：[10.1016/j.oceaneng.2024.119615](https://doi.org/10.1016/j.oceaneng.2024.119615)，其题名明确把积分 wind-up mitigation 与 turning assist 放在同一算法中；由于本次获取到的出版商元数据未含正文，不引用其具体限幅方程。[一手论文元数据；机制方向可作近期交叉证据]

### 1.5 已知风/流：前馈蟹角还是反馈积分

若风/流向量已知且质量可靠，优先把已知分量转换为期望对地航迹角的**前馈蟹角**，再用小积分增益处理模型误差：

\[
\boldsymbol v_g=R(\psi)\boldsymbol v_b+\boldsymbol v_c,
\qquad
\chi_d=\operatorname{atan2}(v_{g,e},v_{g,n}),
\]

或者按已知流速求解满足目标路径切向方向的船体速度向量。前馈的优点是响应快、不会把整个定常流偏差堆进积分；缺点是流场误差、风扰动和速度估计误差会直接进入参考。ILOS 的优点是不要求流场精确，缺点是有积分滞后、饱和和返航过冲风险。[Fossen 2021，current/crab-angle compensation sections；Fossen & Lekkas 2017]

对天气最优航迹，不能把“最小横向误差”与“最小能耗/最小航行时间”混为一谈。若已知风浪流和推进功率模型，可在上层规划器生成 weather-optimal 航向/速度；LOS/ILOS 只负责跟踪该参考。若环境仅部分已知，保留反馈 ILOS，而不要把带噪声的即时流向直接当作硬蟹角。两者也可组合：已知流前馈 + 小积分补偿，风浪随机项交给反馈/扰动观测器。[工程取舍；Fossen 2021 与 Fossen & Lekkas 2017 的组合解释]

### 对本项目的建议

1. **首选组合：固定或缓慢调度的 ILOS + 已知流前馈蟹角 + 航向参考整形器。** 不建议第一步直接上 ALOS；ALOS 适合在固定 \(\Delta\) 与 ILOS 在多速度/流场回归中显示系统性偏差后再接入。
2. 当前 `IntegralLineOfSightGuidance` 已实现
   \[
   \chi_r=\operatorname{atan2}\left[-\left(e/\Delta+K_i z\right),1\right],\quad \dot z=e,
   \]
   且固定 \(\Delta=50\,m\)、\(K_i=10^{-4}\)、积分限值 1000 m、\(|e|\le50\,m\) 才累积。[项目证据：`colav_simulator/modular_gnc/guidance_ilos.py`]
3. 先保留固定 \(\Delta=50\,m\) 作为基线，做 \(\Delta\in[35,66]m\) 和低速/高速分组回归；只有当速度变化造成明确的噪声—切角折中，再采用 \(\Delta(U)=\operatorname{clip}(\Delta_0+k_UU,\Delta_{min},\Delta_{max})\)。
4. 将积分限值从“1000 m 的裸参数”改成可追溯的航向效应限值：记录 \(\theta_I=\arctan(\Delta K_i z)\)，先将 \(|\theta_I|\) 限于约 5°–10° 的仿真候选窗，再以 XTE、舵程和返航超调回归选择；5°–10°是调参窗，不是标准值。
5. 路线切换、避碰返航和急转弯阶段冻结或泄漏积分；接回原路线前使用曲率连续过渡。验收指标应包含 XTE、航向超调、积分贡献角、舵速饱和时间和回线后的 S 形次数。

---

## 二、环境载荷建模范式

### 2.1 风：系数表、相对风、剖面和面积

船体风载的通用工程表达是

\[
\boldsymbol F_w=\frac12\rho_a V_{aw}^2
\begin{bmatrix}
C_X(\gamma_{aw})A_F\\
C_Y(\gamma_{aw})A_L
\end{bmatrix},
\qquad
N_w=\frac12\rho_a V_{aw}^2 C_N(\gamma_{aw})A_L L_{pp}.
\]

\(V_{aw}\) 是相对风速，\(\gamma_{aw}\) 是相对风向角；系数必须与定义的参考面积、参考长度、坐标方向一致。Fossen 教材给出船舶相对风、动压和风力/力矩系数的统一处理；项目旧 `Viknes`/`RVGunnerus` 代码也按该范式计算 \(C_X,C_Y,C_N\)。[Fossen 2021，wind-load chapter；项目证据：`colav_simulator/core/models.py`]

高度修正常用幂律

\[
V(z)=V(z_r)\left(\frac{z}{z_r}\right)^p,
\]

其中海上中性层的工程指数常取约 \(p=1/7\) 作为初始近似；开阔海面、稳定度、阵风和测风高度不同，指数不能当船型常数。IEC/气象规范会按场址和平均风/阵风定义选择剖面，仿真器应把 \(p\)、参考高度和风速类型显式记录。[工程/气象惯例；不应把 1/7 当 OCIMF 对所有 FCB 的强制值]

OCIMF MEG4 官方页面确认：MEG3 的油轮风系数在 MEG4 中保持不变，并认为对双壳油轮可适用于 16,000 DWT；小于该尺度的油轮应考虑船级社规则。来源：[OCIMF, Mooring Equipment Guidelines (MEG4)](https://www.ocimf.org/publications/books/mooring-equipment-guidelines-meg4)。这条来源**不支持**把油轮表直接用于 45 m FCB；对 FCB 应使用风洞/CAD/CFD/实测系数，或把 OCIMF 表作为敏感性边界而非验证真值。[标准适用域限制]

对本船，\(A_F\approx45\,m^2\)、\(A_L\approx180\,m^2\) 可以作为早期仿真的数量级假设，但不是标准典型值：\(A_F\) 对 8 m 宽、约 2 m 吃水的船体加上驾驶室/上层建筑而言可能合理；\(A_L\) 取决于上层建筑高度和遮挡，低矮工作艇可能偏大，封闭式客船/指挥艇则可能合理。建议从 GA/CAD 的最大投影面积和风心高度生成面积资产，至少做 ±30% 面积敏感性；不要用“45/180”替代风系数校准。[工程判断]

### 2.2 流：相对速度和静水阻尼去重

水动力模型应使用船体相对水速度

\[
\boldsymbol\nu_r=\boldsymbol\nu-\boldsymbol\nu_c,
\]

并在科氏/阻尼项中保持同一语义。若选择“相对速度阻尼”策略，流已经通过 \(\nu_r\) 进入静水水动力项，外部 current load 必须为零；若选择“外部流载荷”策略，则用流速与船速形成相对来流，另算系数载荷，同时避免再次把同一流效应放进阻尼。两种做法都存在于工程模型，但必须互斥，否则会 double count。[Fossen 2021，relative-velocity marine model；项目证据：`CurrentStrategy`]

项目已显式提供三种策略：`NONE`、`CURRENT_RELATIVE_DAMPING`、`EXTERNAL_CURRENT_LOAD`；其中 `CURRENT_RELATIVE_DAMPING` 直接返回零外部流载荷，符合“静水阻尼去重”的接口语义。[项目证据：`colav_simulator/modular_gnc/load_model.py`、`contracts.py`]

流载荷的系数、参考面积和矩臂应与风载分开：水下侧面积通常按 \(L_{pp}T\) 或验证过的投影面积，不能直接复用 \(A_L\)。流场若是空间变化，还应在船体参考点采样并记录梯度是否被忽略。[Fossen 2021；工程实现约束]

### 2.3 波：JONSWAP、方向扩展和精度层级

JONSWAP 频谱的常用参数化为

\[
S_J(\omega)=\frac{\alpha g^2}{\omega^5}
\exp\left[-\frac54\left(\frac{\omega_p}{\omega}\right)^4\right]
\gamma^{\exp\left[-\frac{(\omega-\omega_p)^2}{2\sigma^2\omega_p^2}\right]},
\]

其中 \(\gamma\) 是峰值增强因子，\(\sigma=0.07\)（\(\omega\le\omega_p\)）或 0.09（\(\omega>\omega_p\)）是常用分段值。原始一手来源是 Hasselmann 等的 JONSWAP 联合北海观测报告（1973）；ITTC 的官方“Recommended Procedures and Guidelines”索引是程序版本入口：[ITTC procedures index](https://ittc.info/downloads/quality-systems-manual/recommended-procedures-and-guidelines/)。参数 \(\alpha,\omega_p,\gamma\) 应由目标 \(H_s,T_p\) 或风区/风程模型校准；不能只写一个“JONSWAP”标签。[一手观测报告；ITTC 程序入口]

方向扩展应满足归一化

\[
S(\omega,\mu)=S_J(\omega)D(\mu\mid\omega),
\qquad
\int_{-\pi}^{\pi}D(\mu\mid\omega)\,d\mu=1.
\]

工程上常用 \(D\propto\cos^{2s}(\mu-\mu_0)\) 的截断/归一化形式；\(s\) 随频率、风浪发展程度变化。方向扩展形式不是唯一标准，需把 \(D\) 的定义、主向、坐标和归一化写入场资产。[ITTC seakeeping procedures index；工程多方案]

工程仿真可按三层精度区分：

1. **一阶波浪力**：用 Froude–Krylov、绕射/辐射结果和 RAO，在离散频率成分上叠加
   \[
   \boldsymbol\tau^{(1)}(t)=\Re\left\{\hat{\boldsymbol\tau}^{(1)}(\omega_e,\beta) e^{i\omega_e t}\right\}.
   \]
   需要频率、方向、遭遇频率和船体 RAO/载荷资产；适合评估 heave、pitch、roll、瞬时姿态和波频控制扰动。[Fossen 2021，seakeeping/wave-load material；ITTC Recommended Procedures index]
2. **二阶平均漂移力**：用对角近似时，保留每个成分的 \(A_i^2\) 项，例如
   \[
   \bar{\boldsymbol\tau}^{(2)}\approx\sum_i\boldsymbol Q_{ii}(\omega_i,\beta_i)A_i^2.
   \]
   它表达低频/平均的 surge、sway、yaw 载荷，成本低、易用于实时仿真，但忽略交叉频率项。[Fossen 2021；项目 `DIAGONAL_AI2`]
3. **全双频 QTF**：
   \[
   \boldsymbol\tau^{(2)}(t)=\sum_{i,j}\boldsymbol Q(\omega_i,\omega_j,\beta_i,\beta_j)A_iA_j
   \cos((\omega_i-\omega_j)t+\phi_{ij}),
   \]
   可表达差频和和频耦合，适合低频漂移、系泊和精细耐波性，但需要完整 QTF 资产和较高计算/校准成本。[Fossen 2021；ITTC Recommended Procedures index；工程精度层级]

“对角 \(A_i^2\)”不是全双频 QTF 的等价物。前者适合实时、筛选和控制器回归；后者适合最终设计或需要低频漂移统计的研究。项目契约已显式区分 `FIRST_ORDER`、`MEAN_DRIFT`、`BOTH`，并将 `DIAGONAL_AI2` 与 `FULL_PAIR_QTF` 作为不同模型枚举，这是正确的可追溯方向。[项目证据：`contracts.py`、`load_model.py`]

对 45 m 小船、\(H_s=0.5\)–2 m：不能仅由显著波高判断“漂移力”或“滚摇”必然主导；要比较波遭遇频率与 roll/pitch 固有频率、阻尼和航速。8 m/s 下遭遇频率因航速和相对浪向改变，波频一阶 roll/pitch 可能成为姿态与执行器负荷的主导；在低速、长时间保持航迹或斜浪下，二阶平均 sway/yaw 漂移可成为路径偏差的主导低频项。建议控制回归启用“一阶波 + 简化平均漂移”，并分别报告波频姿态 RMS 与低频位置/航向偏置；不能用单一“波浪主导效应”结论替代频率分析。[工程判断；一阶/二阶定义见 Fossen 2021 与 ITTC 程序族]

### 2.4 4DOF 注入和 roll 力臂

对 3DOF/roll-4DOF plant，环境载荷应在船体坐标系组装成

\[
\boldsymbol\tau_{env}^{b}=[X_{env},Y_{env},K_{\phi,env},N_{env}]^T,
\]

再与推进/控制广义力在同一 RHS 中求和；不要把已转换到 body frame 的载荷再次用航向旋转。Fossen 的 3DOF/6DOF 体坐标广义力表示是这一接口语义的依据。[Fossen 2021；项目 `VesselLoad` / `EnvironmentalLoads`]

若侧向力作用点高度为 \(z_F\)，重心高度为 \(KG\)，滚转载荷大小应按

\[
K_\phi=Y\,(z_F-KG)
\]

并保留符号约定。把水下侧向力心近似在静水线下 \(T/3\) 处时，力臂的**量值**可写成 \(|KG-T/3|\)（正上方向定义下的符号由坐标系决定）；\(0.5T\) 是粗略敏感性假设，不是普适标准。风载则应使用上层建筑风心到重心的实际竖向距离，不能复用水下流载荷力臂。[Fossen 2021；项目 `CurrentLoadModel`]

项目当前外部流载荷在缺少 \(C_M^x\) 时使用 `KG - T/3` 自动矩臂；风载使用专门的 `wind_roll_moment_arm_m` 或风心高度。这个区分应保留，并在 trace 中记录力臂来源。[项目证据：`colav_simulator/modular_gnc/load_model.py`]

### 对本项目的建议

1. **风**：保留 `WindCoeffTableAsset`，但将 OCIMF 油轮表只作为“外部边界/敏感性资产”，不标记为 FCB validated。优先建立 0–180° 相对风向的 FCB 风洞/CFD/CAD 系数表，明确 \(C_X,C_Y,C_N\)、参考面积和正负号。
2. **面积**：先用 \(A_F=45\,m^2,A_L=180\,m^2\) 做 baseline，同时跑 ±30% 和风心 ±1 m 敏感性；若路径偏差对面积异常敏感，优先补几何资产而非调 PID。
3. **流**：默认继续使用互斥 `CURRENT_RELATIVE_DAMPING` / `EXTERNAL_CURRENT_LOAD`，禁止两者同时计入同一流效应。路径跟踪场景首选相对速度阻尼 + 已知流前馈蟹角；只有需要系数表可解释载荷时才开 external load。
4. **波**：实时默认 `BOTH`（一阶波 + `DIAGONAL_AI2` 平均漂移），把 `FULL_PAIR_QTF` 留给离线高保真/系泊类回归。验收分离波频 roll/pitch 与低频 XTE/yaw 偏差。
5. **4DOF**：所有环境模块统一输出 body-frame `[Fx,Fy,Kroll,Nyaw]`；roll 矩臂必须带来源字段（风心、`KG-T/3`、或 fallback），不要将 `0.5T` 隐式写死。

---

## 三、舵执行器建模范式

### 3.1 两种表达

舵法向力的基本线性化来自

\[
F_\delta\approx \frac12\rho A_R C_{L\alpha}U_R^2\,\delta,
\qquad
N_\delta\approx x_R F_\delta,
\]

其中 \(U_R\) 是舵处来流速度，\(A_R\) 是舵面积，\(x_R
deep\) 是相对重心的纵向力臂。若舵角较大，应使用非线性 \(C_L(\alpha_R)\)，而不能继续把 \(F_\delta/\delta\) 当常数。[Fossen 2021，rudder and actuator-force material]

**方案 A：舵角作为分配器决策变量。** 执行器向量包含主推力与 \(\delta_i\)，分配器在当前速度/推力线性化

\[
\Delta\boldsymbol\tau
= B(U,T)\begin{bmatrix}\Delta T_1&\Delta T_2&\Delta T_3&\delta_1&\delta_2\end{bmatrix}^{T},
\]

舵列近似为

\[
B_{\delta_i}(U,T)=
\begin{bmatrix}0\\K_{\delta_i}(U,T)\\x_{R_i}K_{\delta_i}(U,T)\end{bmatrix}.
\]

优点是能表达速度、桨后洗流、舵速/舵角约束和双舵分配；缺点是矩阵随状态变化，静态线性 `lstsq` 需要每周期更新或分段更新，并要处理角度变量的非线性和零速退化。[Fossen 2021；工程控制分配]

**方案 B：先分配等效横力/艏摇矩，再由舵律单独求舵角。** 分配器继续输出 `[X,Y,N]`，舵模块用 PD/Nomoto 反演或局部逆模型得到 \(\delta_i\)。优点是与当前接口兼容、容易审计；缺点是分配器不知道真实舵角、舵饱和和舵速饱和，可能产生“广义力可实现、实际舵不可实现”的假象。[工程架构判断]

### 3.2 低速舵效、失速和来流角降额

建议使用

\[
K_\delta(U_R)=\frac12\rho A_R C_{L\alpha}U_R^2\,\sigma(U_R),
\qquad
\sigma(U_R)=\frac{U_R^2}{U_R^2+U_0^2}
\]

作为低速舵效的平滑起点，或用试验数据表替代 sigmoid。\(\sigma\) 不是统一行业标准；它的作用是避免在 \(U_R\to0\) 时线性化矩阵仍宣称拥有高舵效。[工程模型]

失速可用

\[
\alpha_{eff}=\operatorname{clip}(\alpha_R,-\alpha_{stall},\alpha_{stall}),
\qquad
F_R=\frac12\rho A_R U_R^2 C_L(\alpha_{eff})
\]

并在超出失速角时增加降额或滞回。\(\alpha_{stall}\) 取值依赖舵型、空化数、桨后紊流和雷诺数；“来流角达到 25° 时只保留 70% 舵效”可作为保守工程折线，但不是 DNV/ABS/ITTC 对所有舵的通用标准。若没有舵剖面/试验数据，应把 25°/70% 明确标记为假设并做 50%–100% effectiveness sweep。[Fossen 2021；工程多方案]

### 3.3 桨后洗流

简化桨盘诱导速度常写为

\[
u_{wash}=k_w\sqrt{\frac{2T}{\rho A_{disk}}},
\]

其中 \(k_w\) 常被工程模型取约 0.55，再与船体前进速度按具体 wake model 合成 \(U_R\)。0.55 是经验系数，不是船级社统一常数；真实舵来流还受伴流、桨距、桨—舵间距和推力工况影响。Fossen 船舶模型通常使用桨加速/舵处来流项；项目旧模型已有

\[
u_{rud}=u_r+k_u\left(\sqrt{u_r^2+\frac{8T}{\pi\rho d_R^2}}-u_r\right)
\]

的同类结构。[Fossen 2021；项目证据：`main_propeller_rudder_angle_to_lift_force`]

因此不能把 \(u_{wash}=0.55\sqrt{2T/(\rho A_{disk})}\) 与项目现有诱导速度公式叠加两次。应选择一个明确的来流模型，记录 \(k_w\)、桨盘面积和 wake fraction，使用推力/转速单元测试校验单调性。[工程集成约束]

### 3.4 双舵同步还是独立

- **同步舵**：\(\delta_1=\delta_2\)。适合左右对称、正常巡航和第一阶段路径跟踪；参数少、分配矩阵条件更稳定。
- **独立舵**：分别优化 \(\delta_1,\delta_2\)。可表达差动艉力矩、单舵失效、左右来流不一致和低速操纵；代价是更多约束、可能出现舵角相反的非直观解，并需要清晰的舵角/舵速/失速代价。[工程多方案；Fossen 2021 的执行器/控制分配原则]

45 m FCB 有两舵和三主推。若当前任务是服务航速约 8 m/s 的名义航路跟踪，同步舵是合理 baseline；若 COLAV 需要低速急转、单舵故障或差动艉力矩，最终应支持独立舵，至少在 allocator asset 层保留两列而不是永久合并成一列。

### 对本项目的建议

1. **短期低复杂度方案**：保持静态线性 `lstsq` 的 `[X,Y,N]` 接口，把双舵等效为服务航速下的有界横力执行器；在 effectiveness ledger 中记录
   \[
   K_{\delta,0}=\frac12\rho A_R C_{L\alpha}U_{R,0}^2
   \]
   和适用速度窗。该方案适合先验证 planner/ILOS/plant 闭环，不应被标成全速域高保真舵模型。
2. **推荐中期方案**：把分配矩阵扩展为状态调度的 \(B(U,T)\)，至少按 \(U_R^2\)、桨后洗流、舵角边界和舵速边界更新；在接近低速或失速时把舵列 effectiveness 降为零/低值，避免 `lstsq` 继续把不可实现的横力分给舵。
3. **接口取舍**：若不能改变现有 allocator 输入输出，采用“等效横力 + 独立舵后端”时必须将实际舵角、舵速、饱和和 achieved load 回传给 anti-windup；否则 MarinePID 会看到理想 `[Y,N]`，产生 truth leakage 或积分堆积。[项目现有 `AchievedGeneralizedLoad` 契约]
4. **舵效初值**：不要把 25°/70% 和 \(k_w=0.55\) 当标准常数；将它们作为可配置假设，做 \(k_w\in[0.4,0.7]\)、失速降额 50%–100% 和 \(C_{L\alpha}\) ±20% 的敏感性回归。
5. **双舵策略**：第一阶段同步舵；资产格式和内部 actuator state 保留独立 \(\delta_1,\delta_2\) 能力。只有在低速 COLAV、故障注入或实船数据证明差动舵有收益后，才打开独立优化，避免无证据增加 allocator 维度。
6. **验证顺序**：零速/低速舵效趋零；固定 \(U,T\) 时力矩随 \(\delta\) 单调；桨推力增加时舵效增加但不重复计入诱导速度；失速后力不继续线性增长；舵速限幅和延迟对 achieved load 可观测；最终用回转/zigzag 与 Fossen/IMO 操纵性锚点做联测。[Fossen 2021；IMO MSC.137(76) 作为非强制验收锚点，官方决议镜像：[MSC.137(76) PDF](http://doerry.org/norbert/MarineElectricalPowerSystems/references/S_IMO_MSC.137-76/MSC.137(76).pdf)]

---

## 设计决策表

| 决策点 | 选项 | 推荐 | 依据 |
|---|---|---|---|
| 路径导引基线 | Pure pursuit / LOS / ILOS / ALOS | **ILOS + 已知流前馈蟹角** | LOS 是欠驱动船路径跟踪基线；ILOS 对定常流有收敛/实验谱系；ALOS 增加估计器验证成本。[Breivik et al. 2003；Caharija et al. 2016；Fossen & Lekkas 2017] |
| \(\Delta\) | 固定 / \(\Delta_0+k_UU\) / 未约束自适应 | **先固定 50 m，再做有界速度调度** | 无通用标准；50 m=1.13 \(L_{pp}\) 是本船合理基线。速度调度必须有上下限和回归证据。[Fossen 2021；工程判断] |
| ILOS 积分治理 | 无界 / 裸限幅 / 限幅+泄漏+相位冻结 | **限幅+泄漏/冻结+航向效应 trace** | 积分用于定常漂移，但大 XTE/返航切线会 wind-up；文献与近期 Unified LOS 都强调治理。[Caharija et al. 2016；Tanakitkorn et al. 2024] |
| 已知风流补偿 | 纯反馈 ILOS / 纯前馈 / 前馈+小积分 | **前馈蟹角 + 小积分补偿** | 减少积分滞后和长期舵偏，同时保留对流场误差的鲁棒性。[Fossen 2021；Fossen & Lekkas 2017] |
| 风系数 | OCIMF 油轮表 / FCB 专用表 / 常系数 | **FCB 专用资产；OCIMF 仅敏感性边界** | MEG4 明确系数适用双壳油轮至 16,000 DWT，不支持外推 45 m FCB。[OCIMF MEG4] |
| 风面积 | 固定 45/180 m² / CAD 投影 / CFD/风洞 | **CAD 投影起步，45/180 baseline+±30% sweep** | 面积取决于上层建筑和风心，非船型统一常数。[Fossen 2021；工程判断] |
| 流处理 | 相对速度阻尼 / 外部流载荷 / 两者叠加 | **二选一；默认相对速度阻尼** | \(\nu_r=\nu-\nu_c\)；同一流效应叠加会 double count。项目已有互斥策略。[Fossen 2021；项目代码] |
| 波精度 | 仅一阶 / 仅平均漂移 / 一阶+对角 \(A_i^2\) / 全 QTF | **实时一阶+对角平均漂移；离线再上全 QTF** | 一阶覆盖波频 roll/pitch；平均漂移覆盖低频偏置；全 QTF 成本和资产要求更高。[Fossen 2021；ITTC procedures index] |
| 4DOF 环境力 | 只注入 `[X,Y,N]` / body `[X,Y,K,N]` | **统一 body-frame `[Fx,Fy,Kroll,Nyaw]`** | 与 4DOF RHS 及项目 `VesselLoad` 契约一致；矩臂来源必须显式。[Fossen 2021；项目代码] |
| 舵表达 | 舵角进 allocator / 广义力后独立舵律 | **阶段一等效横力，阶段二速度调度舵列** | 现有静态 `lstsq` 先求闭环可解释性；全速域保真需要 \(U_R^2\)、洗流、失速和饱和调度。[Fossen 2021；项目架构] |
| 低速舵效 | 常数 / \(U_R^2\) / \(U_R^2\sigma(U)\) | **\(U_R^2\sigma(U)\)，参数化且可校准** | 舵力随来流平方；低速 sigmoid 是工程正则，不是规范常数。[Fossen 2021；工程判断] |
| 失速/降额 | 不建模 / 硬 clamp / 非线性+降额表 | **先 clamp，后用舵试验表替换** | 25°/70% 仅保守假设，不能冒充 DNV/ABS 通用要求。[Fossen 2021；船舵型依赖] |
| 桨后洗流 | 不计 / \(0.55\sqrt{2T/(\rho A)}\) / 完整推进器模型 | **先单一经验模型，禁止重复诱导；后续校准** | 0.55 是工程经验；项目已有同类 \(k_u\) 模型。[Fossen 2021；项目代码] |
| 双舵 | 同步 / 独立 / 永久合并 | **同步 baseline，资产保留独立列** | 正常巡航同步更稳；低速 COLAV/故障场景需要独立自由度。[工程取舍] |

---

## 参考来源

1. Fossen, T. I., *Handbook of Marine Craft Hydrodynamics and Motion Control*, 2nd ed., Wiley, 2021. DOI：[10.1002/9781119575016](https://doi.org/10.1002/9781119575016)。本报告用于 LOS/ILOS、相对速度模型、风/流/波载荷、舵力与推进器来流的教材级依据。
2. Breivik, M., Fossen, T. I., & Skjetne, R., “Line-of-sight path following of underactuated marine craft,” *IFAC Proceedings Volumes*, 36(21), 211–216, 2003. DOI：[10.1016/S1474-6670(17)37809-6](https://doi.org/10.1016/S1474-6670(17)37809-6)。
3. Caharija, W. et al., “Integral Line-of-Sight Guidance and Control of Underactuated Marine Vehicles: Theory, Simulations, and Experiments,” *IEEE TCST*, 24(5), 1623–1642, 2016. DOI：[10.1109/TCST.2015.2504838](https://doi.org/10.1109/TCST.2015.2504838)。
4. Lekkas, A. M. & Fossen, T. I., “Integral LOS Path Following for Curved Paths Based on a Monotone Cubic Hermite Spline Parametrization,” *IEEE TCST*, 22(6), 2287–2301, 2014. DOI：[10.1109/TCST.2014.2306774](https://doi.org/10.1109/TCST.2014.2306774)。
5. Fossen, T. I., Pettersen, K. Y., & Galeazzi, R., “Line-of-Sight Path Following for Dubins Paths With Adaptive Sideslip Compensation of Drift Forces,” *IEEE TCST*, 23(2), 820–827, 2015. DOI：[10.1109/TCST.2014.2338354](https://doi.org/10.1109/TCST.2014.2338354)。
6. Fossen, T. I. & Lekkas, A. M., “Direct and indirect adaptive integral line-of-sight path-following controllers for marine craft exposed to ocean currents,” *IJACSP*, 31(4), 445–463, 2017. DOI：[10.1002/acs.2550](https://doi.org/10.1002/acs.2550)。
7. Fossen, T. I., “An Adaptive Line-of-Sight (ALOS) Guidance Law for Path Following of Aircraft and Marine Craft,” *IEEE TCST*, 31(6), 2887–2894, 2023. DOI：[10.1109/TCST.2023.3259819](https://doi.org/10.1109/TCST.2023.3259819)。
8. Tanakitkorn, K. et al., “Unified line-of-sight: A guidance algorithm with integral wind-up mitigation and turning assist for USVs,” *Ocean Engineering*, 314, 119615, 2024. DOI：[10.1016/j.oceaneng.2024.119615](https://doi.org/10.1016/j.oceaneng.2024.119615)。
9. OCIMF, *Mooring Equipment Guidelines (MEG4)*, 4th ed., official page：[https://www.ocimf.org/publications/books/mooring-equipment-guidelines-meg4](https://www.ocimf.org/publications/books/mooring-equipment-guidelines-meg4)。页面明确说明 MEG3 油轮风系数沿用，并给出双壳油轮 16,000 DWT 适用边界。
10. ITTC, *Recommended Procedures and Guidelines*，官方程序索引：[https://ittc.info/downloads/quality-systems-manual/recommended-procedures-and-guidelines/](https://ittc.info/downloads/quality-systems-manual/recommended-procedures-and-guidelines/)。报告用作波谱/耐波性/环境载荷程序的版本入口；具体项目应固定当期 procedure number 和 revision。
11. Hasselmann, K. et al., “Measurements of wind-wave growth and swell decay during the Joint North Sea Wave Project (JONSWAP),” *Deutsche Hydrographische Zeitschrift*, A8(12), 1973。JONSWAP 原始观测/谱参数来源；本次未将无法核验的 DOI 写入。
12. IMO, Resolution MSC.137(76), *Standards for Ship Manoeuvrability*, 2002，公开镜像：[http://doerry.org/norbert/MarineElectricalPowerSystems/references/S_IMO_MSC.137-76/MSC.137(76).pdf](http://doerry.org/norbert/MarineElectricalPowerSystems/references/S_IMO_MSC.137-76/MSC.137(76).pdf)。45 m FCB 不属于该决议的一般 100 m 适用范围；本报告仅建议把其作为非强制操纵性回归锚点。

## 核心结论

- **导引**：以固定 50 m ILOS 为可解释基线，叠加已知流前馈蟹角和积分限幅/冻结；ALOS 延后到基线在多速度多流场景证明不足后。
- **环境**：实时采用 body-frame 风/流 + 一阶波与对角平均漂移，流处理严格二选一；OCIMF 油轮系数不直接外推 FCB。
- **舵**：静态 `lstsq` 先用服务航速等效横力，随后按 \(U_R^2\)、桨后洗流、失速和舵速约束扩展速度调度舵效；同步舵先行、独立舵留接口。
