# FCB45 波浪载荷模型：一手来源复核与实施建议

复核日期：2026-09-09
对象：FCB45 名义 45 m、Lpp 44.1 m，4DOF（surge/sway/roll/yaw）工程仿真
边界：只做来源、量纲、模型边界和可实施方案复核；本次不改代码、不运行测试。

## 结论

第一阶段应采用 **FK-only incident-pressure quadrature**：由 Lpp、B、T 和 displacement 生成一个明确的参数化水下船体，运行时在该参数化表面做 Airy 入射压力积分，输出 `[surge, sway, roll, yaw]` 激励力。这个实现不需要实船 RAO，也不需要外部 CAD/面元文件；参数化曲面产生的数值积分点属于模型内部的数值求积，不应被描述为实船 hull mesh。

这条路径保留真实的空间波相位、有限水深色散和 `r × dF` 力矩，足以作为 C-level 工程波激励基线。它仍然只是 incident/Froude-Krylov 部分，不包含 diffraction/scattering、radiation、added mass、radiation damping、slamming 或完整耐波性。FCB45 在 `Tp=7 s` 时深水近似 `lambda≈76.5 m`、`kLpp≈3.6`，因此绕射可能显著；不得把 FK-only 结果称为完整 hydrodynamic validation。

当前一阶 inferred kernel 应停用或仅保留为 legacy comparison：`f_fk_sway` 的代码量纲是 N/m，却作为 N 使用；`f_fk_roll` 的代码量纲是 N m²，却作为 N m 使用；`0.03`、`rao_*` 频率形状和 yaw 的 `sin` 相位没有船体水动力来源。运动 RAO 不能乘在激励力上。波浪激励和运动响应必须分开，运动响应若以后需要，应由含质量、附加质量、阻尼和恢复力的频域/时域方程求得。

没有 FCB45 QTF 或一阶 diffraction/radiation 解时，`mean_drift` 应默认关闭。若产品确实需要一个二阶占位项，只能实现为明确命名的 `momentum_flux_proxy`：使用有量纲的 `rho*g*a_i^2*L_ref` 力尺度、显式无量纲反射/吸收系数和不确定性，按独立分量做 `sum(Q_ii*a_i^2)`。这不是 QTF，也不是船型验证系数；同频或相干方向的交叉项必须等待 QTF。

## 一手来源

| 来源 | 可直接采用的证据 | 对本项目的含义 |
|---|---|---|
| [Capytaine theory manual](https://capytaine.org/stable/theory_manual/theory.html) | 线性势流假设；有限水深 Airy potential、`omega^2 = k g tanh(kh)`；压力面元积分；FK、diffraction、radiation 三项分解；动态阻抗方程 | FK-only 的公式、适用边界和“不能把 RAO 当力”的主来源 |
| [Capytaine `airy_waves.py` source](https://raw.githubusercontent.com/capytaine/capytaine/v2.3.1/src/capytaine/bem/airy_waves.py) | `airy_waves_potential()`、`airy_waves_pressure()` 和 `froude_krylov_force()` 的开放实现；压力由 `i*rho*omega*potential` 得到，再按面元积分 | 可照着实现单位波幅压力和面元求积，不复制 BEM 求解器 |
| [Capytaine `FloatingBody.integrate_pressure`](https://raw.githubusercontent.com/capytaine/capytaine/master/src/capytaine/bodies/bodies.py) | 逐面元使用面积、法向和刚体 DOF；源码明确 `-` 号用于 fluid-on-body force，并支持 rotation DOF | 明确 `dF=-p*n*dS` 和 `dM=r×dF` 的实现方向 |
| [WAMIT User Manual §3.3/§3.5/§3.8](https://www.wamit.com/manualv7.4/wamit_v74manualch3.html) | 激励力、压力、运动 RAO、mean drift 是不同输出；mean drift 为二阶幅值项并有双向波交叉项；质量/阻尼/恢复力方程单独求运动 | 不能把 motion RAO 乘到 FK force；没有 QTF 时只能做显式近似 |
| [WAMIT User Manual §6](https://www.wamit.com/manualv7.4/wamit_v74manualch6.html) | mean drift 可由 control-surface momentum、momentum conservation 或 pressure 计算；二次项对一阶解和水线离散敏感 | mean drift 不是只靠 `A_i^2` 和几何比例就能精确得到 |
| [Lee, “On the evaluation of quadratic forces on stationary bodies”](https://www.wamit.com/Publications/jnn70-chlee.pdf) | Bernoulli 二阶压力、船体 force/moment 面积分和 control-surface momentum conservation 的原式 | 说明二阶漂移需要一阶速度势/动量通量信息；给出 proxy 的物理边界 |
| [MSS `waveForceRAO.m` at fixed commit](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/LIBRARY/environment/waveForceRAO.m) | 明确读取 `vessel.forceRAO`，插值 complex force RAO，再叠加 `Amp*cos(Omega_e*t+phase)` | Fossen/MSS 的力 RAO 是 force asset，不是 motion asset；可作资产接口参考 |
| [MSS `waveMotionRAO.m` at fixed commit](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/LIBRARY/environment/waveMotionRAO.m) | 明确读取 `vessel.motionRAO`，再由 position RAO 乘 `j*Omega_e`、`-Omega_e^2` 得速度和加速度 | motion RAO 是运动链输入，不能作为 excitation-force gain |
| [MSS `encounter.m` at fixed commit](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/LIBRARY/environment/encounter.m) | `Omega_e = Omega - Omega^2*U*cos(chi)/g`，输入是一个船速、一个 encounter angle | 该式适用于固定/准固定 `U` 的查表；不能把每一帧的瞬时 `Omega_e` 直接乘全局时间 |

Capytaine 理论手册同时明确：势流模型假设无黏、不可压、无旋、小波幅、小船体运动和平底水深。它的有限水深入射势为

\[
\Phi_0=-i\frac{g}{\omega}
\frac{\cosh(k(z+h))}{\cosh(kh)}
e^{ik(x\cos\beta+y\sin\beta)},
\qquad \omega^2=kg\tanh(kh),
\]

深水才可以采用 `k=omega^2/g`。Capytaine 的 post-processing 给出

\[
F_j=-\int_\Gamma p\,n\cdot\delta r_j\,dS,
\qquad p=i\rho\omega\Phi,
\]

并把力拆成 `F_FK + F_D + F_R`；辐射力满足

\[
F_{R,j}=\sum_k(\omega^2 A_{jk}+i\omega B_{jk})X_k.
\]

后一式正是“motion RAO 不能作为 force multiplier”的边界：`X_k` 先进入系统阻抗，不能反过来无依据地缩放 `F_FK`。

## 当前工作树的直接问题

| 位置 | 现状 | 风险 |
|---|---|---|
| [`load_model.py#L1210-L1274`](../../colav_simulator/modular_gnc/load_model.py#L1210) | 以 `k=omega^2/g`、`B*L*k` 构造 `f_fk_sway`；随后乘 `rao_surge/sway/yaw` | 没有空间压力积分；代码结果是 N/m；motion-like filter 被伪装为 force response |
| [`load_model.py#L1231-L1240`](../../colav_simulator/modular_gnc/load_model.py#L1231) | `a*rho*g*B^2*L*((1-exp(-k*T))/k)*0.03` 作为 roll moment | 量纲为 N m²；`0.03` 没有来源；roll lever 没有 `r×F` |
| [`load_model.py#L1319-L1364`](../../colav_simulator/modular_gnc/load_model.py#L1319) | 向量化实现重复上述公式，使用 `phase_t=omega_e*t+phases` | 船速/航向变化时重新计算瞬时遇频并乘绝对时间，会造成相位不连续或错误累计 |
| [`load_model.py#L1493-L1557`](../../colav_simulator/modular_gnc/load_model.py#L1493) | mean drift 使用 `inferred_*_scale`、`freq_shape` 和 KG/T 经验 lever | 输出可量纲化，但系数不是 QTF、Kochin 或 momentum-control-surface 结果 |
| [`load_model.py#L1757-L1793`](../../colav_simulator/modular_gnc/load_model.py#L1757) | `FULL_PAIR_QTF` 明确 `NotImplemented`，默认 `DIAGONAL_AI2` | 当前接口已经承认没有 QTF；不应给 diagonal asset 增加“物理精确”语义 |
| [`environment.py#L60-L109`](../../colav_simulator/modular_gnc/environment.py#L60) | 组件由 JONSWAP-like 频谱生成，幅值为 `sqrt(2*S*dOmega)`，另有无来源 `0.65` 因子 | `wave_significant_height_m` 不一定等于离散组件实际 `Hm0`；需启用能量归一化或记录实际值 |
| [`environment.py#L338-L371`](../../colav_simulator/modular_gnc/environment.py#L338) | `sample_at(position_ne=...)` 接收位置但当前忽略位置 | 波场不是空间场；FK 积分必须从船体世界坐标显式计算相位 |
| [`catalog.py#L582-L597`](../../colav_simulator/modular_gnc/catalog.py#L582) | 默认 `wave_mode=both`，绑定两个 inferred asset；`Hs=1 m,Tp=7 s` | 不能把工程场景先验和 FCB45 波浪校准混同；P0 应先 `first_order`，mean drift 关闭 |

## 仅用 FCB45 设计参数的参数化船体

采用项目当前环境参数：

\[
L=44.1\ \mathrm m,\quad B=8\ \mathrm m,\quad T=2\ \mathrm m,\quad
m=220000\ \mathrm{kg},\quad \rho=1025\ \mathrm{kg/m^3}.
\]

排水体积为

\[
\nabla=m/\rho\approx214.6\ \mathrm{m^3},
\qquad C_B=\frac{\nabla}{LBT}\approx0.304.
\]

若把名称中的 45 m 当作计算长度，`C_B≈0.298`；两者都应记录在 asset provenance，不能静默混用。该较低 block coefficient 与快速/工作船的工程假设相符，但不能从四个输入参数推出真实艏艉线型。

可以用对称椭圆站剖面生成可重复的求积曲面。令 `xi=2*x/L`、`q(x)=max(1-xi^2,0)`，水线半宽和局部吃水为

\[
b_w(x)=\frac B2 q(x)^{p_b/2},
\qquad
d(x)=T q(x)^{p_d/2}.
\]

每个站使用水线到龙骨的半椭圆剖面：

\[
y=\pm b_w(x)\cos\vartheta,
\qquad z=-d(x)\sin\vartheta,
\qquad 0\le\vartheta\le\frac\pi2.
\]

其水下站面积为 `A_s(x)=pi*b_w(x)*d(x)/2`。选择 `p_b,p_d` 使

\[
\int_{-L/2}^{L/2} A_s(x)\,dx=\nabla;
\]

`p_b≈4`、`p_d` 约 4.5–5 可作为起始形状，再以体积方程冻结，而不是直接宣称该形状是 FCB45。对参数面做 Gauss 或规则求积，计算每个点的单位外法向 `n_q`、面积权重 `A_q` 和相对 CG 坐标 `r_q^b`。水线附近和艏艉端点应使用收敛检查；任何数值点密度都属于 engineering discretization assumption。

`KG=2.2 m` 和 `GM=1.5 m` 不进入固定船体 FK pressure 的幅值。`GM` 只进入 4DOF roll restoring，例如

\[
C_{44}=m g GM\approx3.2373\times10^6\ \mathrm{N\,m/rad},
\]

`KG` 用于 CG、惯量和力矩参考点；若以 about-CG 的 `r_q` 做 `r×dF`，KG 只影响几何参考关系。不能用 `GM` 产生一个未来源的 roll RAO，再乘在 wave force 上。

## 推荐的一阶 FK-only 运行时公式

对每个波组件保存：幅值 `a_i`、固有/绝对频率约定、传播方向 `beta_i`、初始相位 `epsilon_i`。令世界水平传播向量为

\[
d_i^n=(\cos\beta_i,\sin\beta_i),
\]

船体点的世界坐标为

\[
x_q^n(t)=x_{CG}^n(t)+R_z(\psi(t))r_q^b.
\]

采用“世界坐标中波峰向 `d` 传播”的约定时，连续相位是

\[
\theta_{iq}(t)=k_i(d_i^n)^T x_q^n(t)-\omega_i t+\epsilon_i.
\]

静水或第一阶段恒定流场中，`k_i` 解有限水深色散；若水很深才使用 `k_i=omega_i^2/g`。若组件频率是固定坐标系绝对频率、同时存在均匀流 `U_c^n`，应明确采用

\[
(\omega_i-k_i(d_i^n)^TU_c^n)^2=gk_i\tanh(k_i h),
\]

并在 asset metadata 写清 `omega_absolute` 或 `omega_intrinsic`。不能一边把 current 当作环境载荷，一边又用没有约定的 `omega_e` 修改波相位。

入射势和压力的实数形式为

\[
\Phi_{iq}=-i\frac{g a_i}{\omega_i}
\frac{\cosh(k_i(z_q+h))}{\cosh(k_i h)}
e^{ik_i(d_i^n)^T x_q^n},
\]

\[
p_{iq}(t)=\Re\{i\rho\omega_i\Phi_{iq}e^{-i\omega_i t+i\epsilon_i}\}
=\rho g a_i\frac{\cosh(k_i(z_q+h))}{\cosh(k_i h)}\cos\theta_{iq}(t).
\]

若 `n_q` 取“从船体指向流体”的外法向，流体对船体的微元力和微元力矩为

\[
dF_{iq}^b=-p_{iq}(t)n_q^b A_q,
\qquad
dM_{iq}^b=r_q^b\times dF_{iq}^b.
\]

最终只取 4DOF 分量：

\[
\tau_{wave}^b(t)=\sum_{i,q}
[dF_x^b,dF_y^b,dM_x^b,dM_z^b]^T.
\]

若工程代码使用相反法向或 FRD z 轴，必须在单独的 frame adapter 中转换并用 cardinal-wave sign check 固定，不在 wave kernel 内塞“蟹角”或 `0.03` 修正。

### 相位和遇频实现边界

`k*d·x(t)-omega*t` 是首选；它自然包含船舶移动和转向。若代码没有世界位置，只能维护相位状态：

\[
\theta_i(t+\Delta t)=\theta_i(t)+
\int_t^{t+\Delta t}(k_i d_i^T\dot x_{CG}^n(\tau)-\omega_i)\,d\tau.
\]

遇频 `omega_e` 可以作为固定/准固定 force asset 的查表坐标，但不能在每一帧把新的 `omega_e` 乘以绝对 `t`。这一点与 MSS `encounter.m` 的固定速度公式并不矛盾：MSS 的公式是一个常速 encounter transformation，不是变速船的相位积分器。

不要给 yaw/roll 强行插入 `sin(phase)` 作为“90 degree lag”。相位由每个面元的空间压力和真实 `r×dF` 产生；需要 complex phase 的 force asset 时，phase 必须来自 FK/diffraction 解或明确校准数据。

## 没有 QTF 时的 mean drift 边界

WAMIT §3.8 对双向同频波写出如下结构：

\[
\bar F_i \propto |A_1|^2F_i(\beta_1,\beta_1)
 +|A_2|^2F_i(\beta_2,\beta_2)
 +2\Re[A_1A_2^*F_i(\beta_1,\beta_2)].
\]

Capytaine 的 mean-drift 章节也要求用 diffraction 与所有 radiation contributions 构造 Kochin function。两者都说明：`Q_ii` 不是仅由 L、B、T、KG、GM 唯一决定的常数；完整系数需要一阶散射/辐射场、控制面动量或压力二阶项。

可接受的工程占位形式是：

\[
E_i=\frac12\rho g a_i^2,
\qquad
\bar F_i^b=C_{m,i}\,\ell_i\,R_i^b d_i^b,
\qquad
\bar M_i^b=r_{eff,i}^b\times\bar F_i^b,
\]

其中 `E_i` 是规则波平均能量面密度，`R_i` 是选定水深 convention 下的线性 radiation-stress/momentum-flux tensor，单位 N/m。若采用二维水平 radiation-stress 约定，可显式写成

\[
R_i=E_i\left[(n_i-\tfrac12)I_2+n_i d_i d_i^T\right],
\qquad n_i=C_{g,i}/C_i,
\]

这里 `n` 是群速与相速之比；`ell_i` 是明确的受波投影长度，例如参数化矩形水线的初始选择 `ell_i=L|sin(gamma_i)|+B|cos(gamma_i)|`；`C_m,i` 是有符号的无量纲反射/吸收工程系数。这个 `R*ell` 只是控制面动量通量的 engineering proxy，`C_m` 仍需假设或校准，不能把它写成 WAMIT/Capytaine 的 exact drift coefficient。也可以直接写成 WAMIT 的量纲尺度：

\[
\bar F_i=\rho g a_i^2 L_{ref}c_{F,i},
\qquad
\bar M_i=\rho g a_i^2 L_{ref}^2c_{M,i}.
\]

推荐规则：

1. 默认 `wave_mode=first_order`，关闭 mean drift；这是没有 QTF 时最诚实的 product baseline。
2. 若必须打开，asset/model 名称必须是 `momentum_flux_proxy`，并记录 `C_m`、`ell`、水深、方向 convention、上下界和 `engineering_assumption` provenance。`C_m=0` 是可审查的零基线；任意 `0.35/0.75` 之类比例不能伪装成标准值。
3. 只对统计独立、长时间平均的组件做 diagonal `sum(Q_ii*a_i^2)`。同频同向或相干方向组件不能丢掉交叉项；需要慢漂移时必须提供 QTF 或等价的一阶场数据。
4. mean drift 不带一阶 `cos(theta)` 相位，也不复用 first-order phase；若需要 difference-frequency slow drift，那已经是 pair-QTF 模型。
5. 当前参数化船体是前后、左右对称的；在没有 asymmetry/QTF 的情况下，proxy 的 yaw/roll mean moment 默认置零。任何 `KG/T` effective lever 必须单独记录为工程假设，不能从对称 hull 自动推出。
6. `max_force_n`/`max_moment_nm` 只能是明确的 actuator/safety saturation，不能拿来掩盖漂移系数或量纲问题。

## 建议落地顺序

1. 新增一个 provenance 明确的 `fk_parametric_inferred` first-order asset；删除或隔离旧 `rao_*` force multiplier，不改变 4DOF plant 的 roll restoring 接口。
2. 在 asset binding 时生成参数化曲面求积点；冻结 `L,B,T,displacement,rho,CG reference,water depth,normal/frame convention` 和 volume residual。
3. 把 wave load kernel 改为 `phase_at_world_point -> pressure -> dF -> r×dF`；环境 field 或 load adapter 必须消费 CG 的世界位置，不能继续忽略 `position_ne`。
4. 记录每个组件的 `a,omega,k,beta,phase`、实际离散 `Hm0`、`ak`/`kL` 和 force/moment units。若保留 JONSWAP-like 场，启用 `normalize_wave_energy` 或明确报告实际 `Hm0`；无来源的 `0.65` 只能作为场景假设。
5. 先做 FK-only focused acceptance：零幅值、振幅加倍线性、空间平移一波长不变、四个 cardinal headings sign、面元加密收敛、变速/转向相位连续、roll/yaw 由 `r×dF` 产生。
6. 后续若要完整一阶 excitation，在同一参数化船体上离线运行 Capytaine/Nemoh，保存 `F_FK`、`F_D`、`F_ex`、added mass/radiation damping 和 convention metadata。只有那时才可讨论 FCB45-specific force RAO/motion RAO；不要把离线 motion RAO 再乘回已含 excitation 的运行时力。

## 验收边界

通过 FK-only focused checks 只能证明：Airy 入射压力、空间相位、面元积分、力矩 frame 和量纲在选定参数化船体上自洽。它不能证明 FCB45 实船耐波性、绕射、辐射、QTF、slamming 或风浪流联合海试结果。

现有默认场景的风/流扰动也应与波浪分开取证：当前环境用按 tick 的无状态 PRF 生成 current perturbation，且没有 `∂v_c/∂t`/空间梯度接口；在 full relative-water 验收前应将其设为零或恒定流。任何固定“蟹角”都不能代替由当前、船速、艏向和实际 sideslip 得出的相对速度；波模块只产生 wave load，不修改 ILOS/PID heading reference。
