# FCB45 full GNC 栈复核与一手来源

复核日期：2026-09-09

对象：45 m FCB、`modular_gnc`、4DOF（surge/sway/roll/yaw）+ ILOS + PID + 3 主推/2 舵，首侧推仅低速
边界：本文件只做来源复核、公式核对和实施建议；不改代码、不运行测试。

## 结论先行

当前工作树已经具备可运行的 4DOF 接口、ILOS/PID 框架、环境轴和 FCB45 执行器试作，但还不能称为“完整物理 FCB45 stack”。原因是四个直接的语义或物理边界：

1. `GenericRoll4DOFPlant` 是能量稳定的通用 surrogate，不是 Fossen 意义上的 FCB45 relative-water hydrodynamic model。它把合并质量矩阵用于一个简化的 `C(ν)`，水动力阻尼仍看船体绝对速度；没有 `νr`、`CA(νr)`、`M_A ν̇c` 或流场导数接口。[项目证据：[`plant.py`](../../colav_simulator/modular_gnc/plant.py#L428-L485), [`plant.py`](../../colav_simulator/modular_gnc/plant.py#L685-L853)]
2. `CurrentLoadModel` 在 `EXTERNAL_CURRENT_LOAD` 下已经按 `νc−ν` 计算一套完整相对流载荷，而 4DOF plant 同时继续施加 `D(ν)ν`；零流时 current component 仍可非零，因而存在额外静水阻力和潜在双计。[项目证据：[`load_model.py`](../../colav_simulator/modular_gnc/load_model.py#L964-L1055)]
3. 当前 ILOS 变量和 trace 自称 `course_reference`，但 `DirectReference.values[2]` 下游始终被 `MarinePID` 当作 `heading`/`ψ`，没有 course autopilot 或 sideslip 转换。`χ` 与 `ψ` 在有风浪流、横漂时不是同一个量。[项目证据：[`guidance_ilos.py`](../../colav_simulator/modular_gnc/guidance_ilos.py#L237-L297), [`controller.py`](../../colav_simulator/modular_gnc/controller.py#L411-L449)]
4. 当前 inferred wave first-order kernel 的 `f_fk_sway` 量纲是 N/m，`f_fk_roll` 量纲是 N·m²；它再乘未经来源校准的运动形状 `rao_*`。同时 `phase_t = ωe(t)t + phase` 在变速/转向时错误地把瞬时遇频乘以全局时间。[项目证据：[`load_model.py`](../../colav_simulator/modular_gnc/load_model.py#L1210-L1274), [`load_model.py`](../../colav_simulator/modular_gnc/load_model.py#L1319-L1364)]

建议的最小完整路径是：先把 current 和 wave 的物理边界修正，再把 rudder 从“静态等效横力”提升为“真实舵角状态 + 局部来流力”，最后才做 9 场景闭环验收。FCB45 参数可以继续使用同事设计估计作为 C-level 仿真输入，但每个参数必须带 `engineering_assumption`/`vendor_config` provenance，不能借用 MSS 的其他船参数并称为 FCB45 校准。

## 来源和许可

| 来源 | 本次核验内容 | 许可/使用边界 |
|---|---|---|
| [Fossen Marine Craft Model](https://fossen.biz/html/marineCraftModel.html) | 6DOF relative-current 方程、`νr=ν−νc`、绝对速度积分时的 `ν̇c`、有限/简化相对方程 | 教材/网页受版权保护；引用公式和语义，不能把教材内容当项目代码许可 |
| [MSS，固定 commit 98970f7](https://github.com/cybergalactic/MSS/tree/98970f71a21cfe81e7e29abdcc1bb6741789cddc) | `ILOSpsi.m`、4DOF `navalvessel.m`、4DOF roll/rudder `container.m`、6DOF current `otter.m`、风和波工具 | 仓库 [`LICENSE`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/LICENSE) 是 MIT；若复制代码，保留版权和许可文本 |
| [PythonVehicleSimulator，固定 commit 6073346](https://github.com/cybergalactic/PythonVehicleSimulator/tree/6073346c86180087d3bca608b1aa2bc08be59708) | Python 车辆类、相对流、PID/参考模型示例 | GitHub 标注 MIT；其 [`LICENSE`](https://github.com/cybergalactic/PythonVehicleSimulator/blob/6073346c86180087d3bca608b1aa2bc08be59708/LICENSE) 的版权行来自 Python Packaging Authority，复制前应保留原文并做法务/依赖复核 |
| [Fossen et al. 2015 论文](https://www.fossen.biz/publications/2015%20Fossen%20et%20al%20TCST.pdf) | ALOS、4DOF surge-sway-roll-yaw 模型、heading PID 和舵机动态 | 论文版权按出版物处理；只复现方程和引用，不复制长段落 |
| [Sørensen, Sagatun & Fossen 1996](https://www.fossen.biz/publications/1996%20Sorensen%20et%20al%20CEP.pdf) | current relative velocity、风力向量、波一阶/二阶层级、波辐射与低频阻尼边界 | 论文版权按出版物处理 |
| [Capytaine 2.3 theory manual](https://capytaine.org/stable/theory_manual/theory.html) 和 [`airy_waves` source](https://capytaine.org/master/_modules/capytaine/bem/airy_waves.html) | Airy 势、有限水深色散、压力积分、FK/diffraction/radiation 分解 | 当前 Capytaine README 声明 v3 起 Apache-2.0；[`README`](https://github.com/capytaine/capytaine/blob/master/README.md) 与生成资产的第三方数据仍需单独记录 |
| [Nemoh v3 documentation](https://lheea.gitlab.io/Nemoh/) | 开源 BEM、first-order、QTF 输出路径 | [Nemoh manual](https://gitlab.com/lheea/Nemoh/-/blob/a898182935eb6132ea75e5113ce9b9070ef3237e/Documentation/Nemoh_Manual.tex) 声明 GPL-3.0；建议只把它作为离线工具，不把 GPL 源码嵌入本仓库 |
| [Fujiwara, Ueno & Nimura 1998 DOI](https://doi.org/10.2534/jjasnaoe1968.1998.77)；[NMRI 作者页面](https://www.nmri.go.jp/archives/institutes/marine_renewable_energy/marine_energy_research/staff/fujiwara/fujiwaraen.html) | 船型几何风力回归和 heel moment 研究来源 | 论文/数据表版权按原出版物处理；不能将通用/油轮表标成 FCB45 validated |
| [OCIMF MEG4 official page](https://www.ocimf.org/publications/books/mooring-equipment-guidelines-meg4) | MEG4 的油轮风系数适用域 | 官方页面的适用对象是油轮；不能外推为 45 m FCB 的验证系数 |

MSS 还明确列出 `navalvessel` 为 51.3/51.5 m 的 nonlinear surge-sway-roll-yaw 模型、`container` 为 175 m 的 nonlinear roll model；这些文件非常适合复用方程组织和接口，却不能提供 FCB45 的数值参数。[MSS catalog](https://www.fossen.biz/MSS/)、[`navalvessel.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/CRAFT/SHIP/models/navalvessel.m)、[`container.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/CRAFT/SHIP/models/container.m)

## ILOS：必须先统一 `ψ` 和 `χ`

### 一手实现的原式

MSS 的 [`ILOSpsi.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/GNC/ILOSpsi.m) 明确输出 `psi_ref`，代码注释给出经典 ILOS 离散更新：

\[
\psi_d[k]=\pi_h-\tan^{-1}\left(K_p\left(y_e[k]+\kappa y_{int}[k]\right)\right),\quad K_p=1/\Delta,
\]

\[
y_{int}[k+1]=y_{int}[k]+h\Delta\frac{y_e[k]}
{\Delta^2+(y_e[k]+\kappa y_{int}[k])^2}.
\]

源码还要求 `R_switch <` 相邻航点距离，路段切换后继续最后一个航向；2024 revision 增加了给 `LOSobserver` 的参考整形接口。这个实现是 heading ILOS，不能把它的 `psi_ref` 叫 COG。

MSS 的 [`LOSchi.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/GNC/LOSchi.m) 才是 course law，输出 `chi_ref = pi_h - atan(y_e/Delta_h)`。Fossen et al. 2015 进一步写明

\[
\chi=\psi+\beta,\qquad \beta=\operatorname{atan2}(v,u),
\]

并在其 ALOS 4DOF 案例中用 heading autopilot 追踪 `ψd`；ALOS 的更新量估计 sideslip，heading PID 的积分则解决 heading loop 自己的 bias 和未建模动态。[论文第 3 节及第 5 页](https://www.fossen.biz/publications/2015%20Fossen%20et%20al%20TCST.pdf)

### 本项目缺陷和最小修复

`IntegralLineOfSightGuidance.compute_reference()` 当前使用

\[
\chi_r=\operatorname{atan2}\left(-\left(e/\Delta+K_i I\right),1\right),\quad \dot I=e,
\]

然后写入 `DirectReference.values[2]`。`MarinePID._extract_signals()` 和 `_shape_heading_reference()` 都把该元素作为 heading，误差是 `reference.values[2] - measurement.heading_rad`。这在 calm water、横漂接近零时不容易暴露，在 current/wind/wave 下会把 course correction 误当成船首航向。

最小可实施方案：

1. 保持现有下游 PID 接口为 heading，字段改名为 `heading_reference_rad`，trace 同步改名；ILOS 采用 MSS `ILOSpsi` 的离散式，或逐式证明当前缩放状态与该式等价后再保留自定义形式。
2. 如果产品确实需要输出 `chi_d`，增加独立 course autopilot：用测得/估计的 sideslip `β_hat` 形成 `ψ_d = chi_d - β_hat`，再交给 heading PID。不得直接把 `chi_d` 写进 heading 通道。
3. 已知流只做可追溯前馈 `β_hat`，未知/变化部分由 ILOS/ALOS 补偿；不写一个固定的“蟹角常数”。
4. 低速 `U≈0` 时，暂停 sideslip/ILOS 积分并保持最后有效航向，避免 `atan2(v,u)` 和 path tangent 在静止状态制造伪估计。

可验证条件：

- 无流、无风、直线、初始横向偏置：项目 ILOS 输出与 MSS `ILOSpsi` 逐步 parity，误差为零或在明确浮点容差内。
- 恒定横流：船首 `ψ` 可以与航迹切线有稳定偏置，但 COG `χ` 收敛到航迹切线；trace 同时记录 `ψ_d`、`χ`、`β_hat`，不把三者混为一个字段。
- 路线 revision/segment 切换：积分状态按既有生命周期规则清零，切换不产生未经整形的航向阶跃。

## 4DOF relative-water：完整模型和 external delta 边界

### 一手方程

Fossen 官方 [Marine Craft Model](https://fossen.biz/html/marineCraftModel.html) 给出带不可旋转海流的方程：

\[
M_{RB}\dot\nu+C_{RB}(\nu)\nu+M_A\dot\nu_r+C_A(\nu_r)\nu_r+D(\nu_r)\nu_r+g(\eta)
=\tau+\tau_{wind}+\tau_{wave},
\]

其中 `νr = ν−νc`，`νc=[uc,vc,wc,0,0,0]`。对于 body frame 中由恒定 NED 海流旋转得到的 2D current：

\[
u_c=V_c\cos(\beta_c-\psi),\qquad
v_c=V_c\sin(\beta_c-\psi),
\]

\[
\dot{\nu}_c^b=[r v_c,-r u_c,0,0]^T.
\]

官方网页给出的绝对速度积分形式是

\[
\dot\nu=
\begin{bmatrix}-S(\nu_2)v_c^b\\0_{3\times1}\end{bmatrix}
+M^{-1}\left(\tau+\tau_{wind}+\tau_{wave}
-C(\nu_r)\nu_r-D(\nu_r)\nu_r-g(\eta)\right),
\]

这里使用了对线速度独立的 `C_RB^{ν2}` 参数化。MSS [`otter.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/CRAFT/USV/models/otter.m) 给出同一实现边界：`nu_r = nu - nu_c`、`nu_c_dot = -Smtrx(nu2)*nu_c`、`CA = m2c(MA,nu_r)`，最后在绝对速度导数中加 `nu_c_dot`。

Fossen et al. 2015 的 4DOF ALOS 案例采用

\[
\dot\eta=J(\eta)\nu,\qquad
M\dot\nu+C_{RB}(\nu)\nu+N(\nu_r)\nu_r+g(\eta)=\tau_c,
\]

`η=[N,E,φ,ψ]`、`ν=[u,v,p,r]`、`νc=[uc,vc,0,0]`，`N(νr)=CA(νr)+D(νr)`。论文中的 4DOF 数值来自 multirole naval vessel，不得移植为 FCB45 数值。[论文第 5 页](https://www.fossen.biz/publications/2015%20Fossen%20et%20al%20TCST.pdf)

### 现状 double count

当前 4DOF RHS 使用 `C(ν)`、`D(ν)ν`，而 `CurrentLoadModel` 在 external 模式使用 `νc−ν` 的二次 current force。于是：

- `νc=0` 时，`CurrentLoadModel` 仍可能返回一套非零 current force；
- 同一船体的静水阻力已经在 plant `D(ν)ν` 中，再加一套 current asset 阻力；
- `current_relative_damping` 与 `external_current_load` 的枚举互斥，只能防止两种模块同时声明，不能修复“external full relative load + plant calm damping”的内部重复。

### 推荐选择

**主推荐：把 FCB45 full stack 设为 plant-owned relative-water。** Plant 接收 environment current sample，按 `νr` 计算 `CA/D`，使用 `C_RB(ν)` 的一致参数化，并按所选方程形式一致地处理 `ν̇c`。在未简化的质量矩阵分拆中，`M_Aν̇c` 会移到 RHS；在 Fossen 的简化绝对速度积分中，`ν̇c` 作为 `M⁻¹` 外的项出现。两者只能选一种，不能同时加。primary stack 中 `CurrentLoadModel` 不再把一套完整相对阻尼作为 external load 注入 RHS；它可以保留一个“diagnostic current effect”差值供 trace 展示。

**短期兼容方案：external incremental current。** 若暂时不能改变 plant 输入接口，current asset 只能返回增量：

\[
\Delta\tau_c=F_{cw}(\nu_c-\nu)-F_{cw}(-\nu).
\]

这样 `νc=0` 时严格为零。该方案只有在 `F_cw` 与 plant 所代表的 calm-water map 在力的定义、符号、尺度和耦合项上相同才等价于 full relative-water。当前 inferred/table current coefficient 与 plant `D/C` 不是同一 map，所以即使采用 delta 也只能标为 approximate viscous/current disturbance，不能称为完整 Fossen relative model。

external delta 方案中不要再额外加入 `M_Aν̇c`：它把 current acceleration 当成外力映射的一部分。若改为 plant split model，才使用 `ν̇c`；不能同时使用 full relative current load、delta current load 和 current acceleration correction。

### Current field 的时间边界

当前 `AnalyticEnvironmentField` 的 current perturbation 按 tick 由无状态 PRF 生成，空间位置未参与 sample；这不是可微的流场，也没有 `∂v_c/∂t` 或 `∇v_c`。完整 relative-water first milestone 应把 `current_perturbation_std=(0,0)`，使用 NED 中恒定 current。之后如要随机流，使用可 snapshot 的 OU/低通过程并为 plant 提供

\[
\dot v_c^b=R^T(\partial_t v_c^n+(\nabla v_c^n)\dot x)-S(\omega^b)v_c^b.
\]

没有这个导数时，随机 current 只能作为 load disturbance 近似，不能宣称满足完整 relative-water 方程。

可验证条件：

- `current=(0,0)` 时，current component 为零；同一初始状态下，启用 current module 与关闭 current module 的加速度逐通道一致。
- 恒定流时，`νr`、`ν̇c`、`C_A(νr)`、`D(νr)` 在 trace 中可见，且 kinematics 使用绝对 `ν`，不能用 `νr` 直接更新 N/E。
- 外部 delta 模式的零流 invariant 精确通过；full relative 模式不再同时把完整 current load 注入 plant。
- current 强度和流向扫描不会出现由于每 tick 白噪声导数缺失而产生的非物理高频 `p/r` 峰。

## 风：来源系数、from/to 适配和 roll 符号

### 来源公式

MSS [`blendermann94.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/LIBRARY/environment/blendermann94.m) 使用 signed relative angle `gamma_r`：

\[
C_X=-C_{DlAF}\frac{\cos\gamma_r}{den},\quad
C_Y=C_{Dt}\frac{\sin\gamma_r}{den},\quad
C_K=\kappa(s_H/H_m)C_Y,
\]

\[
C_N=\left(s_L/L_{oa}-0.18(\gamma_r-\pi/2)\right)C_Y,
\]

随后使用 `τX=0.5ρ_a C_X V_r² A_F`、`τY=0.5ρ_a C_Y V_r² A_L`、`τN=0.5ρ_a C_N V_r² A_L L_{oa}`。MSS [`isherwood72.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/LIBRARY/environment/isherwood72.m) 还明确把角度折到 0–180°，再用 `sign(gamma_r)` 恢复横向/艏摇符号。

Fujiwara et al. 的公开论文和后续 NMRI 资料采用另一套几何回归表达，典型水平面形式为

\[
C_X=X_0+X_1\cos\beta+X_3\cos3\beta+X_5\cos5\beta,
\]
\[
C_Y=Y_1\sin\beta+Y_3\sin3\beta+Y_5\sin5\beta,
\quad
C_N=N_1\sin\beta+N_2\sin2\beta+N_3\sin3\beta.
\]

\[
X_A=\tfrac12\rho_a A_F U_A^2C_X,\quad
Y_A=\tfrac12\rho_a A_L U_A^2C_Y,\quad
N_A=\tfrac12\rho_a A_L L_{OA}U_A^2C_N.
\]

这套回归的 `β` 常以 **0° 为 head wind、180° 为 following wind** 定义；论文中的几何项和力矩参考点必须随原式一并实现。45 m FCB 不应直接使用油轮 OCIMF 表，也不应把 Fujiwara 系数当成 FCB45 validated；应以 FCB45 的 `A_F/A_L`、风心高度、上层建筑几何和敏感性区间生成 provisional asset。Fujiwara 1998 论文说明该方法来自多船型风洞回归，却没有赋予任意新船型自动验证资格。

若当前没有完整 FCB45 风洞/CAD 回归输入，最小可实施候选是直接采用 MSS `blendermann94.m` 的公式，并选其 `vessel_no=14`（speed boat）作为类型先验；这比仓库内没有来源的 `_OCIMF_ROWS` 更可追溯，但仍只能标为 `semi_empirical/mock` 和敏感性基线。不得把 speed-boat row 14 叫作 Fujiwara，也不得把它叫作 FCB45 validated。拿到 FCB45 的上层建筑几何后，再切换到 Fujiwara 1998 的几何回归或实测/CAD/CFD 系数；两套公式和 angle convention 不要混在同一资产中。

### 当前适配风险

项目 `WindSample` 明确是 `NE-to` 向量，`WindLoadModel` 计算 `v_air_to^b - v_ship^b` 后直接用 `atan2(rel_v, rel_u)` 查表。[`contracts.py`](../../colav_simulator/modular_gnc/contracts.py#L171-L200), [`load_model.py`](../../colav_simulator/modular_gnc/load_model.py#L923-L960)]

如果表的角度是 Fujiwara/Blendermann 的 from-angle（0° head），应先构造

\[
v_{air,from}^b=v_{ship}^b-v_{air,to}^b,
\]

再用项目明确的 `β_from` 查表。若表定义的是传播/to-angle（0° following），直接使用 `v_air_to^b-v_ship^b` 才可能正确。两者相差 180°；当前 `_OCIMF_ROWS` 的 0° 和 180° 数值也不构成可证明的对称关系，不能靠“把表旋转 180°”修复。

实施时应保留一个单独的 `WindAngleConvention`/adapter，记录：source convention、field convention、body axis、signed angle range、表的参考点。不要在 load kernel 内隐含翻转。

### Roll 力矩

项目 `VesselLoad` 定义 body FRD：x forward、y starboard、z down，`roll_nm` 为绕 x 的 starboard-down 正方向。[`contracts.py`](../../colav_simulator/modular_gnc/contracts.py#L576-L619)] 对作用点 `r_F^b=(x_F,y_F,z_F)` 和 body force `F^b`，统一使用

\[
\tau_F^b=r_F^b\times F^b,
\qquad
K_x=y_FF_z-z_FF_y.
\]

纯侧向力且以 signed body-down 坐标表示时：

- 力作用在 CG 上方：`z_F<0`，所以 `K_x=−z_F F_y`；若输入正的 above-CG arm `h_up=−z_F`，则 `K_x=+h_up F_y`。
- 力作用在 CG 下方：`z_F>0`，所以 `K_x=−z_F F_y`；若输入正的 below-CG arm `h_down=z_F`，则 `K_x=−h_down F_y`。

当前 wind 使用 `K=-Fy*positive arm`，current 使用 `K=+Fy*(KG−T/3)`；这两个表达都没有显式声明 arm 是 signed z 还是 above/below magnitude，并与 `r×F` 的 FRD 定义不一致。修复方式是把风心、流力心、波力心都转换为相对 CG 的 signed `z_F` 后统一叉乘。若波/风表已经给出 about-CG 的 `K`/`C_K`，禁止再次乘力臂。

可验证条件：施加相同 `+Fy`：above-CG 产生 `+K_x`，below-CG 产生 `−K_x`；四个 cardinal wind vectors 的 `X/Y/N` 方向符合 from/to 约定；零风力矩全为零。

## 波浪：替换当前 inferred first-order kernel

### 当前问题

当前 first-order inferred kernel：

\[
f_{sway}=a\rho gBLk e^{-kT/2}
\]

量纲为 N/m，而代码把它直接作为力；roll 项

\[
f_{roll}=a\rho g(B^2/4)L\frac{1-e^{-kT}}{k}\times0.03
\]

量纲为 N·m²，而代码把它作为 N·m。`0.03` 没有物理来源。随后 `rao_surge/sway/yaw/roll` 只是自定义频率形状，不是由 added mass、radiation damping、diffraction 或 FCB45 RAO 求得的 transfer function。即便维度修正，也不能把 motion-response filter 当作 excitation-force filter。

环境 field 的 `sample_at(position_ne=...)` 当前忽略位置；wave component 只有 `ω、phase、direction`，load kernel 使用 `phase_t=ωe*t+phase`。在船速/航向改变时，瞬时 `ωe` 不应直接乘全局 `t`，会导致相位跳变或错误累计。

### 推荐来源和两级实现

Fossen MSS 的 [`waveForceRAO.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/LIBRARY/environment/waveForceRAO.m) 提供了正确的 **资产驱动** 结构：把 RAO 幅值/相位转换成 complex real/imag，按频率和相对方向插值，使用 `Ω_e=|Ω−kU cosβ|`，最后叠加 `|RAO| Amp cos(Ω_e t+angle(RAO)+phase)`。该写法的隐含边界是一个计算调用中 `U`、方向和 RAO reference 固定/准固定；不能把它解释成任意变速船的 `ωe(t)t` 通用积分器。

Capytaine 官方理论给出更适合本项目的离线资产路径：

1. 有限水深 Airy potential
   \[
   \Phi_0=-i\frac{g}{\omega}
   \frac{\cosh(k(z+h))}{\cosh(kh)}
   e^{ik(x\cos\beta+y\sin\beta)},
   \quad \omega^2=kg\tanh(kh).
   \]
   深水才可简化为 `k=ω²/g`。
2. 线性压力
   \[
   p=i\rho\omega\Phi_0.
   \]
3. 面元/面板积分
   \[
   F_i=\int_\Gamma p\,n\cdot\delta r_i\,dS.
   \]
   对 FCB45 4DOF，可直接取 `[X,Y,K_x,N_z]` 的 rigid-body displacement/moment arm；或先积分 `F=∫p n dS`，再用 `r×F`。

**Level 1（现在可实施）：FK-only 面元资产。** 从 FCB45 简化或 CAD 水下 mesh 读取面元中心、面积、outward normal 和相对 CG 坐标；离线对 `(ω, wave_direction)` 计算 complex `[X,Y,K,N]` FK amplitude，运行时只做相位叠加。该模型清楚标记 `fk_only`，不声称包含 diffraction、radiation、QTF 或完整耐波性。

**Level 2（推荐的完整环境资产）：Capytaine/Nemoh 离线生成 excitation/RAO。** Capytaine 能计算 added mass、radiation damping、diffraction、FK、total excitation 和 RAO；Nemoh v3 还提供 QTF。运行时保存 FCB45 专用 `F_ex(ω,β)`、必要的 radiation/RAO/QTF metadata；不要在运行时把已经包含 response 的数据再乘一遍 `rao_*`。

对于当前 4DOF plant，first-order 运行时应接收 **wave excitation load**。如果未来另建 wave-frequency motion model，则 motion RAO 作为运动输入，不能再把 motion output 当 force 注入同一个 LF plant。

### 相位、遇频和方向

对世界坐标中向 `d_i=(cosβ_i,sinβ_i)` 传播的波，建议使用

\[
\theta_i(t)=k_i d_i^T x^n(t)-\omega_i t+\epsilon_i.
\]

如果使用固定 body/RAO 的准稳态实现，则应维护相位状态并按

\[
\theta_i(t+\Delta t)=\theta_i(t)+\int_t^{t+\Delta t}
\left(k_i d_i^T\dot x^n(\tau)-\omega_i\right)d\tau
\]

更新，而不是 `omega_e_current * absolute_time`。Fossen MSS 的 `waveForceRAO` 使用 `Ω_e t` 是其固定 `U`/heading 计算设定下的实现；Capytaine 使用 `e^{-iωt}` phasor，明确说明相位与 WAMIT 的 `e^{+iωt}` 不同，导入资产必须记录 convention。[Capytaine conventions](https://capytaine.org/stable/user_manual/conventions.html)

当前 `direction_to_rad` 与 Capytaine 的传播方向定义可对齐：Capytaine `β=0` 表示从 `x=-∞` 向 `x=+∞` 传播，`β=π/2` 表示沿正 y 传播。若某 RAO 文件使用 incoming/from direction，转换一次并把转换写入 asset metadata。

### 二阶 mean drift

Sørensen et al. 1996 明确区分一阶波力与二阶 mean/slowly varying drift：一阶与波幅成正比，二阶 drift 与 `A_i²` 成正比；Newman/diagonal 近似能降低成本，但会产生高频无物理意义的分量，完整 QTF 则需要更多输入。[论文第 5 节](https://www.fossen.biz/publications/1996%20Sorensen%20et%20al%20CEP.pdf)

因此：

- 当前 `DIAGONAL_AI2` 结构可以保留为接口，但 coefficient 必须来自 FCB45/Nemoh/QTF 或明确的量纲正确反射动量通量近似；当前任意 `freq_shape`、`inferred_*_scale` 只能是 provisional。
- 一阶波力和 mean drift 分开记录、分开验收；不要给 mean drift 复用一阶波相位。
- 没有可信 drift asset 时，先关闭 mean drift；`BOTH` 只有在 first-order excitation asset 和 drift asset 都有来源时才作为完整环境档。

可验证条件：

- FK 面元/RAO 每个输出列的单位分别为 N 或 N·m，随机 wave amplitude 加倍时 first-order force 加倍。
- 同一固定船速下，phase 与 MSS/Capytaine reference 的单分量波形逐周期一致；船移动后用 `k·x−ωt` 的相位不随转向突跳。
- `wave_mode=first_order` 不读取 drift asset；`mean_drift` 不产生一阶波频力；wave asset 内已有 excitation/response 时不再乘第二个运动 RAO。
- `roll` 以 about-CG 的 `K_x` 输入 plant，或由面元 `r×F` 生成；不得使用无量纲 `0.03` 作为隐藏修正。

## 3 主推 + 2 舵 + 低速首侧推

### 来源模式

MSS [`container.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/CRAFT/SHIP/models/container.m) 给出完整的舵/桨后流结构：

- `uP` 根据船速、横漂/艉部运动和 wake 计算桨后来流；
- `uR = uP*epsilon*sqrt(1 + 8*kappa*KT/(pi*J^2))`；
- `alphaR = delta + atan(vR/uR)`；
- `FN` 随 `uR²+vR²` 和 `sin(alphaR)` 变化；
- 同一个 `FN` 同时生成 X/Y/K/N；
- `delta_c` 先限幅，`delta_dot` 再限舵速。

MSS [`navalvessel.m`](https://github.com/cybergalactic/MSS/blob/98970f71a21cfe81e7e29abdcc1bb6741789cddc/CRAFT/SHIP/models/navalvessel.m) 直接展示 4DOF 外力接口 `[Xe,Ye,Ke,Ne]`、roll/yaw 水动力耦合和 `K`/`N` 的分别计算。Fossen 2015 论文的舵机模型也是饱和舵角加一阶/速率受限动态，而不是每 tick 直接把期望力当作已执行力。

### FCB45 最小物理执行器

当前工作树的 `fcb45_actuation.py` 已按同事配置加入了 3 mains、2 rudders、2 bow tunnels 的 `v2` 试作，参数如下；这些是同事设计估计，尚非海试校准：

| 参数 | C-level 起始值 | 语义 |
|---|---:|---|
| rudder area | 3.5 m² each | 舵面积 |
| `C_Lα` | 2.8 rad⁻¹ | 小角度线性升力斜率 |
| rudder angle | ±0.6109 rad | 舵角 envelope |
| rudder rate | 0.1 rad/s | 舵角速率 envelope |
| main force rate | 200 kN/s | 主推实际力速率 |
| bow force rate | 50 kN/s | 首侧推实际力速率 |
| bow derate start | 1.5 m/s | 开始降额 |
| bow re-enable/unlock | 2.7 m/s | 上升后锁定状态解除的下行阈值 |
| bow lockout | 3.2 m/s | 上升时锁定阈值 |

对每个 rudder，应由实际执行舵角和局部相对来流计算：

\[
U_{R,i}=\operatorname{wash}(u_{r},T_{i},x_i),\quad
\alpha_{R,i}=\delta_i+\operatorname{atan2}(v_{R,i},u_{R,i}),
\]
\[
F_{N,i}=\tfrac12\rho A_R U_{R,i}^2 C_L(\alpha_{R,i}),
\quad
\tau_{R,i}=r_{R,i}\times F_{R,i}.
\]

第一阶段可用 `C_L=C_Lα α` 加失速角 clamp；`U_R²` 使低速舵效自然趋近零。`k_w≈0.55` 这类桨盘 wash 系数只能是显式工程假设，且一套来流公式只允许计一次；不得把 MSS 结构和同事已有的 accelerated speed 再串联成双重诱导。

当前实现仍有一个 full-stack 缺口：`FCB45ActuatorTrace`/`ActuatorDynamicsTrace` 的 achieved load 是 `[X,Y,N]`，rudder 的实际力没有形成 `roll_nm`；plant 也拒绝控制 roll channel。若舵力作用点在 CG 下方，至少应把实际 rudder force 的 `K_x` 作为未控环境/执行器耦合项写入 4DOF RHS，或扩展 achieved-load contract 明确区分“控制请求不含 roll”和“执行器真实 roll reaction”。否则 4DOF roll 只响应风浪，不能称为完整 rudder–roll hydrodynamics。[项目证据：[`fcb45_actuation.py`](../../colav_simulator/modular_gnc/fcb45_actuation.py#L221-L335), [`plant.py`](../../colav_simulator/modular_gnc/plant.py#L632-L661)]

### 首侧推 lockout

当前 v2 的 hysteresis 方向是合理的：低于 unlock 才重新启用，超过 lockout 才锁定；但必须把它定义为 allocator 的 active-set/policy，而不是给 plant 一枚持续存在的理想横向力。建议：

1. `U_gate` 采用明确的 through-water speed 或 ground speed，并写入 trace；涉及 current 时不能在 allocator 和 actuator 使用两种不同速度。
2. `U_gate ≤ 1.5`：bow authority=1；`1.5 < U_gate < 3.2`：连续降额；`U_gate ≥ 3.2`：authority=0 且进入 locked；下降至 `≤2.7` 才 re-enable。
3. 使用平滑 bounded function（例如 smoothstep）产生 authority；锁定区间命令强制为零，且 allocator 的 `B(U,T)` 和 actuator force limit 同时反映零能力。
4. 高速（包括 8 m/s nominal service speed）不得使用首侧推；高速度横向/艏摇由两舵和 3 主推差动承担。第一版不设置高速度 emergency unlock，以免把“仅低速使用”变成隐藏旁路。
5. 分配器必须回传 bow lockout/derate 原因和 achieved residual；PID anti-windup 使用实际 achieved load，不能把被 lockout 的请求视为已执行。

可验证条件：速度 sweep `[0,1.5,2.7,3.2,8]` 中 authority 单调、状态具有 hysteresis、8 m/s 首侧推实际输出严格为零；在低速 rudder `U_R→0` 时舵力趋零而 bow 可承担 sway/yaw；主推速率和舵速率都能在 trace 中观测。

## 建议修复顺序

### P0：先修复会改变物理结论的错误

1. **Wave**：禁用当前 inferred first-order kernel，或将其仅留作 legacy comparison；接入 FK-only 面元 asset。删除量纲错误的 `f_fk_*` 和未经来源的 `rao_*` force filter；改用有限水深 dispersion、绝对空间相位和 explicit convention。
2. **Current**：在 full stack 选 plant-owned relative-water；先把 current perturbation 设为恒定，加入 `νr`/`ν̇c`；若短期保留 external，改为 `F(νc−ν)−F(−ν)` 并把它标为 approximate increment。
3. **Wind**：确定 source table 是 from 还是 to；使用 vector adapter；替换无来源/不对称的 OCIMF mock rows 或将其明确限定为 mock sensitivity；统一 `K_x=r×F`。
4. **ILOS**：把输出明确改成 heading `ψd`，采用 MSS `ILOSpsi` parity；或新增 course autopilot 让 course 和 heading 成为两个显式信号。

### P1：形成可解释的 FCB45 plant/actuator

5. 用 MSS `navalvessel` 的 4DOF 方程组织，把同事 FCB45 参数（包括 `I_x`、`K_phi`、`d_p`、`d_pp`、mass couplings）填入 ownship asset；先用 free-roll period/decay、straight-line 和 turning regression 验证。`d_p≈1e7`、`d_pp≈5e7` 可作为同事 C-level 起点，但不是标准值。
6. 把 3 main + 2 rudder + 2 bow 的控制变量分为真实舵角/主推力/首侧推力；plant 只接收实际执行结果。双舵保留独立 state，正常巡航可以同步 command。
7. 在 dynamic `B(U,T)` 中体现 rudder `U_R²`、wake、angle/rate/stall；低速 bow policy 由 allocator/actuator 统一拥有。

### P2：资产和系统验收

8. Capytaine/Nemoh offline pipeline：mesh、water depth、frequency/direction grid、FK/diffraction/radiation/QTF convention、hash 和 provenance 一起输出。Capytaine Apache 可作为默认离线候选；Nemoh GPL 只通过外部工具使用。
9. 按组件做 focused contract，再跑 full closed-loop：

   - current zero-flow and constant-flow parity；
   - wind cardinal sign/roll arm；
   - single wave phase/dimension/energy；
   - rudder force/rate/wash/stall and bow gate；
   - ILOS `ψ/χ/β` trace；
   - OT/HO/CS × VO/Fan-MPC/Mid-MPC 9 场景，检查 actual solver、actual actuator load、无 fallback、无 collision/grounding、clearance/XTE/recovery。

只有 P0 条件通过后，S10 的 9/9 避碰结果才可以被解释为“在物理一致环境下的 full-stack evidence”；之前的结果仍然有效地证明当前 3DOF/PID/避碰闭环可运行，但不能证明 4DOF relative-water、真实波激励或全速域舵效。

## 参考文件和源码索引

1. Fossen, T. I. [Marine Craft Model](https://fossen.biz/html/marineCraftModel.html).
2. Fossen, T. I. [Marine Systems Simulator (MSS)](https://github.com/cybergalactic/MSS/tree/98970f71a21cfe81e7e29abdcc1bb6741789cddc), MIT, commit `98970f71a21cfe81e7e29abdcc1bb6741789cddc`.
3. Fossen, T. I. [Python Vehicle Simulator](https://github.com/cybergalactic/PythonVehicleSimulator/tree/6073346c86180087d3bca608b1aa2bc08be59708), commit `6073346c86180087d3bca608b1aa2bc08be59708`.
4. Fossen, T. I. et al. [Line-of-Sight Path Following for Dubins Paths With Adaptive Sideslip Compensation of Drift Forces](https://www.fossen.biz/publications/2015%20Fossen%20et%20al%20TCST.pdf), IEEE TCST 23(2), 2015, DOI [10.1109/TCST.2014.2338354](https://doi.org/10.1109/TCST.2014.2338354).
5. Caharija, W. et al. [Integral Line-of-Sight Guidance and Control of Underactuated Marine Vehicles](https://doi.org/10.1109/TCST.2015.2504838), IEEE TCST 24(5), 2016.
6. Sørensen, A. J. et al. [Design of a Dynamic Positioning System Using Model-Based Control](https://www.fossen.biz/publications/1996%20Sorensen%20et%20al%20CEP.pdf), Control Engineering Practice 4(3), 1996.
7. [Capytaine theory manual](https://capytaine.org/stable/theory_manual/theory.html), [Airy-wave source](https://capytaine.org/master/_modules/capytaine/bem/airy_waves.html), [conventions](https://capytaine.org/stable/user_manual/conventions.html), Apache-2.0 since v3.
8. [Nemoh documentation](https://lheea.gitlab.io/Nemoh/), [manual/license](https://gitlab.com/lheea/Nemoh/-/blob/a898182935eb6132ea75e5113ce9b9070ef3237e/Documentation/Nemoh_Manual.tex), GPL-3.0.
9. Fujiwara, T., Ueno, M. & Nimura, T. [Estimation of Wind Forces and Moments acting on Ships](https://doi.org/10.2534/jjasnaoe1968.1998.77), Journal of the Society of Naval Architects of Japan 183, 1998.
