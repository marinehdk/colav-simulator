# Spec: GNC Full-Stack Integration — FCB45 4DOF + ILOS + PID + 3主推2舵 + 环境 (V2)

日期: 2026-09-05 · 状态: PUBLISHED → Issue #68 https://github.com/marinehdk/colav-simulator/issues/68（research 已并入；调研档 docs/research/2026-09-05-gnc-los-env-rudder-integration-survey.md）
来源会话: GNC集成验收：GNC功能修复-2 (sess_0330fa1e) + 本会话侦察

## 1. 目标

面向三种避碰算法（vo / potocnik_colreg_fan_mpc / mid_mpc_ipopt）的验证，交付一套完整卡片插件式 GNC 栈：

```
fcb45_roll_4dof_plant                      # 4DOF（surge/sway/roll/yaw）真实 FCB45 参数
+ integral_line_of_sight                   # LOS 导引（路径跟踪）
+ fcb45_marine_pid                         # PID 控制器（已有）
+ data_driven_allocator[fcb45_main_rudder_actuator_layout_v1]     # 3 主推 + 2 舵（新增布局）
+ resolved_actuator_dynamics[同布局]        # 执行器动力学（新增舵速率限）
+ analytic_environment_field + standard_environmental_load        # 风浪流环境（新增轴）
```

同事 L4-5 源码仅作参考，不照搬 ROS 节点/策略层；全部落点必须是现有卡片（module_axes/registry/stack catalog/资产）架构的常规扩展。

## 2. 现状核实（侦察结论，均已在本会话验证）

已有（勿重做）：
- `fcb45_roll_4dof_plant`：catalog tier 4，全参数档（catalog.py:213-236，restoring_k_phi=3.2373e6）
- `integral_line_of_sight`：guidance_ilos.py，χd=α+atan2(-(e/Δ+Ki·I),1)，积分饱和/阈值/trace/snapshot 齐备
- `fcb45_marine_pid`：极点配置增益+Mz(u) 供应商帽（Issue #67 slice 6）
- 4 布局资产：default_triple / quad_diagonal / main_only / fcb45_actuator_layout_v1（3 主推+2 首侧推，无舵）
- `analytic_environment_field` + `standard_environmental_load`：registry 条目、stack.from_config 装配、phase 链（environment→…→plant）全通；load_model 含 OCIMF 风/相对流/JONSWAP+对角 Ai² 漂移内核与默认资产
- runner 链路：`_inject_ownship_gnc_stack` 按 catalog 注入 ship_modules（runner.py:957-973）——catalog 扩展后 runner 零改动

冒烟实测（本会话，seed 11，dt 0.1）：
- 目标栈（ILOS+4DOF+PID+env wind 6m/s/current 0.4m/s/Hs 1.0m mean_drift）直线 600s：max|XTE|=0.04m（env off 为 0.00m）
- roll 有响应：max|φ|=0.044°（GM 刚性恢复下量级合理）
- `_extract_4dof_env_load` 的 [surge,sway,roll,yaw] 映射正确（plant.py:664-682），无顺序 bug

缺口（本 spec 交付）：
1. `_candidate_configs()` 不枚举环境模块 → 82 栈无一含环境；`module_axes()` 无 environment 轴
2. 无舵布局（舵角语义/供应商坐标缺失）
3. catalog 无 env 模块 canonical 参数档（field 气象参数 + load_model 船体几何）
4. GUI 环境卡为硬编码锁定占位（config-shell.js gncRenderCards('gncEnvironmentChoices', …) 静态 calm_water）
5. 目标栈无验收战役（straight/zigzag 锚点 env on/off + 三算法九宫格）

## 3. 设计决策

| # | 决策点 | 决定 | 理由 |
|---|---|---|---|
| D1 | 环境轴阶梯 | 两档：Tier0 Calm water（当前缺省，env 模块缺席，82 个既有 stack_id 不变）→ Tier1 Analytic wind/current/wave（field+load_model 配对，wave_mode=mean_drift） | stack_id 由 identity 拼接，同 identity 不同 wave_mode 参数会撞 id；wave-off 档留 CLI RunSpec 参数 override，不占产品卡位 |
| D2 | 环境轴与栈组合 | 环境模块配对追加到所有现有组合（枚举笛卡尔积 ×2），无效组合由现有 from_config 校验自动过滤 | 复用既有组合枚举+验证机制；GUI 匹配按 role/identity 自动生效 |
| D3 | 流策略 | `current_strategy=external_current_load`（显式外力） | 默认 CURRENT_RELATIVE_DAMPING 下 load model 不出流力（smoke 实证 curr=0）。调研默认推荐"相对速度阻尼"的前提是 plant 水动力消耗 ν_r（Fossen 范式），而本项目 plant 阻尼静态、不感知相对流——external load 是本项目唯一让流实际生效的路径；互斥语义由 registry 既有校验保证（load_model.py/contracts.py），不 double count |
| D4 | 舵建模 | 力有界等效执行器进现有布局资产 schema：kind=rudder，position (-19.594,±3.0)，orientation=−π/2（正指令=右转，Mz=+|x|F 与同事 B 矩阵符号一致），力界 ±180 kN（同事 dynamics 帽；≈service speed 全舵升力 306kN/rad×0.61rad 线性化） | 零 allocator 改动（静态线性 lstsq 不变）；调研佐证此为推荐阶段一方案（等效横力+ledger 记 K_δ,0 与适用速度窗），阶段二 B(U,T) 速度调度（U_R²/洗流/失速/舵速界）延后；双舵同步为 baseline、布局保留两独立舵列（调研 §3.4） |
| D5 | 舵速率限 | resolved dynamics 参数跟随 v1 neutral 惯例（1e9/0 tick，已核实 fcb45_actuator_layout_v1 即如此）；真实舵速率 30 kN/s（=0.1 rad/s 供应商舵角速率 × 306 kN/rad 线性化）与主推 200 kN/s 写入 ledger/provenance，不进参数 | 与 v1 惯例一致（O1 已核实），避免单方面引入行为变化 |
| D6 | 首侧推 | 新布局不含首侧推（用户定义真实船 = 3 主推+2 舵）；v1（3+2 tunnel）保留 | 遵用户船型定义；vendor config 另列 bow tunnel 的事实记 ledger |
| D7 | ILOS 参数 | 沿用默认（Δ=50m≈1.13 Lpp，Ki=1e-4，max integral 1000m，阈值 50m，vmax 10m/s）；不新增 fcb45 变体 identity | 冒烟 max XTE 0.04m；调研佐证 50m 为本船合理首轮测试点（35-66m 窗），Δ(U) 调度须有界扫描+回归证据后再上；ILOS 既有饱和/阈值/路线重置即调研推荐的积分治理三件套；ALOS 延后至基线在多速度/流场回归中显示系统性偏差之后 |
| D8 | 环境参数档 | field：wind (6,2) m/s、pert (0.5,0.5)；current (0.4,−0.2)、pert (0.1,0.1)、external 策略；Hs 1.0m、Tp 7s、24 分量、spread 0.3。load：Lpp44.1/B8/T2.0/Af45/Al180/220t/GM1.5/KG2.2、current_strategy=external_current_load、wave_mode=both + default_inferred_wave_response_v1 + default_inferred_diagonal_drift_v1（已验证装配） | colleague C_mock 面积+本项目 plant preset 几何；T 取 2.0 与 plant 一致（同事 env 用 1.55，差异入 ledger）；wave BOTH=一阶+对角 Ai² 漂移（调研实时默认推荐；一阶给 roll 通道真实波频激励，仅 mean_drift 时 roll≈0.04° 近乎装饰）；Af/Al 记 ±30% 敏感性 ledger；OCIMF 风表按 MEG4 适用域不得标 FCB validated（调研引 MEG4：油轮系数适用双壳油轮≥16000 DWT）；provenance=scenario_assumption/vendor_config |
| D9 | plant/controller 兼容规则 | `_product_transit_compatible` 增加环境无关规则（env 不改 task 面）；env 仅与真实 plant 组合？否——全组合放开，generic 栈吃 FCB45 env 几何属 scaffold 语义（同 marine_pid 先例） | 简单一致；provenance 已按 identity 透传 |

## 4. 交付物

1. **catalog.py**：`_CANDIDATE_*` 增 env 配对枚举；`_CANONICAL_MODULE_PARAMETERS` 增 `analytic_environment_field` / `standard_environmental_load` 两档参数；`_module_axes()` 增 `environment` 轴（calm tier0 + analytic tier1，含 models/expected_effect 文案与 provenance）；参数 provenance 表补两条（DP-10 惯例）
2. **allocator.py**：`_FCB45_MAIN_RUDDER_ACTUATORS`（3 主推+2 舵）+ `fcb45_main_rudder_actuator_layout_v1` 资产（trust/provenance 与 fcb45_actuator_layout_v1 同惯例）+ KNOWN 注册；ledger 条目（D4/D5/D6 偏差）
3. **前端**：config-shell.js `gncEnvironmentChoices` 从 axes.environment 渲染（解除硬编码锁定）、gncSelection/gncStackMatchesSelection 增 environment 角色、cache-bust 全 bump
4. **测试**：
   - 单元：新布局资产内容 hash/信任级/B 矩阵列符号（舵列 sway/yaw 臂、无 roll 行）；env 参数档装配；枚举含 env 的 stack id 存在性与撞 id 回归（同 identity 双 wave 档禁止）
   - facade 锚点：目标栈 straight XTE（calm ≤10m + env on ≤10m）；zigzag 10/10 超调 ≤10°（env off）；env 力分量 sanity（wind/drift 非零、current 经 external 策略非零、roll 响应）
   - GUI node 测试：环境卡渲染/选择/匹配
   - 验收战役：九宫格式 OT/HO/CS × vo/fan_mpc/mid_mpc @目标栈（env on），门沿用 Issue #67：goal、无碰撞/搁浅、min center dist ≥180m、返航 |XTE| ≤50m、穿越 ≤2
5. **GUI YAML contract / evidence 文档**：自动随 catalog（零改动预期，验证之）

## 5. 不做（Out of scope，ledger 记录）

- 同事 Homing/ALOS/转弯速度表/DP 交接/航线仲裁（导引闸门族，未来证据门）
- 分配器 box-QP/PGD、侧推 lockout、Fy 牺牲降级（策略层）
- NDO/SMC/增益调度（控制器增值模块，未来证据门）
- 舵 u² 调度、舵角决策变量、失速/来流降额、桨后洗流
- 全双频 QTF 卷积、Cummins 辐射记忆、每场景环境参数 UI
- target 船动力学/环境（仅 ownship 栈）

## 6. 验收标准（AC）

- AC1 catalog 列出含 `analytic_environment_field+standard_environmental_load` 的栈（数量 = 既有合法组合数），无 stack_id 冲突；`module_axes().environment` 两档文案/provenance 齐备
- AC2 目标栈 id 存在于 catalog 且 GUI 选择卡可复现匹配（node 测试）
- AC3 新舵布局资产：内容 hash 稳定、trust≠validated、B 矩阵舵列 [0,∓1,±|x|] 符号正确、无 roll 行（RA-12）；resolved 参数含真实舵速率
- AC4 facade 锚点：straight max|XTE| calm ≤10m / env-on ≤10m；zigzag 超调 ≤10°（10/10）；env 力分量 sanity 断言（wind/current/一阶波/漂移均非零，roll 出现波频量级响应）
- AC5 九宫格战役 9/9 过 Issue #67 门（env on 目标栈）；既有 82 栈 ids 与其 evidence 文档零变化（快照回归）
- AC6 全套 pytest（除 3 个已知基线失败）+ node 测试绿

## 7. Research 佐证结论（docs/research/2026-09-05-gnc-los-env-rudder-integration-survey.md）

- LOS：ILOS+固定 Δ 为欠驱动船路径跟踪基线（Breivik 2003/Caharija 2016 谱系）；50m=1.13 Lpp 落在建议首轮窗；积分治理=限幅+泄漏/冻结+trace（ILOS 既有实现即满足）；ALOS 延后
- 环境：MEG4 官方页面明确 OCIMF 油轮风系数适用双壳油轮（≥16,000 DWT），不支持外推 45m FCB → provenance 措辞受此约束；流处理互斥是 Fossen 范式（ν_r=ν−ν_c）；wave 精度三层级中对角 Ai² 是实时推荐档；4DOF 注入统一 body-frame [Fx,Fy,Kφ,Nψ]（项目 VesselLoad 契约已符合）
- 舵：调研决策表"舵表达"推荐=阶段一等效横力+ledger、阶段二 U_R²/洗流/失速/舵速调度；双舵同步 baseline+资产保留独立列；IMO MSC.137(76) 可作非强制操纵性锚点（45m 船非强制适用域）

## 8. 开放问题

- O1 ~~resolved 参数惯例~~ → 已核实：v1 用 neutral 1e9/0，新布局跟随（见 D5）
- O2 env 轴是否限制在 FCB45 plant 组合（D9 决定全放开）——实施时若 generic+env 装配失败由枚举过滤兜底
