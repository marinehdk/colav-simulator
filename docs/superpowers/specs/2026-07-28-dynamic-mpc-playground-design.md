# Spec: 动态 MPC 避碰 Playground 工程设计

> **创建**: 2026-07-28
> **分支**: `codex/colav-backend-algorithms` (worktree: `/Users/marine/Code/.worktrees/Colav-Simulator/colav-backend-algorithms`)
> **状态**: Codex 工程评审终稿（2026-07-28）
> **评审基线**: `ba47a8f8cc48d17a665f01f1447a9bf79a4dfd28`
> **上游方案包**: `docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md`
> **设计日志**: `docs/superpowers/design-logs/2026-07-27-dynamic-mpc-playground-design-log.md` (3344 行, 含 VR-01..31 裁决 + R1..R79 证据)
> **能力矩阵基线**: `Design/Algorithm-Capability-Matrix.md`

---

## 0. 阅读须知 (Codex 评审专用)

本 Spec 是**工程实施设计**,不是方案探索。核心技术决策已通过 design-grounding 严裁(VR-01..31)+ DESIGN-IT-TWICE 压力测试(DP-08/19/21/22/24/25/30)+ 用户确认。本 Spec 的职责边界:

### 0.1 本 Spec 可做

- 工程细节设计:架构、组件、数据流、错误处理、测试策略
- 已裁决方案内的工程优化与拔高
- 6-Phase 切分与依赖排序
- 现状代码审计与缺陷分级

### 0.2 本 Spec 不可做 (契约边界)

- **不可推翻 VR-01..31** — 除非发现**新矛盾证据**(须回炉 design-grounding 重新裁决,而非在本 Spec 改)
- **不可重提 ALT-01..18** — 已弃用方案,弃用理由见方案包组件 6
- **不可修改技术规约** — 坐标系/单位/符号约定(方案包组件 2)冻结,需改则回 design-grounding

### 0.3 Codex 评审范围

请评审:
1. **工程合理性**:Phase 切分依赖关系是否正确?出口准则是否可验证?缺陷分级是否合理?
2. **契约一致性**:Spec 内容是否与 VR-01..31 一致?是否触碰禁忌(推翻/重提/改规约)?
3. **现状准确性**:Spec 引用的现状代码事实是否准确?
4. **可实施性**:每 Phase 的工程任务是否可在 executing-plans 阶段落地为 TDD task?

**不要评审**:VR-01..31 本身的裁决正确性(已通过 design-grounding 闭环)、ALT-01..18 弃用决策、技术规约选择。这些属上游 design-grounding 范围。

### 0.4 置信度声明

- 现状代码引用(`RunSpec`/`ICOLAV`/`classify_geometry` 等):🟢 High — 直接读代码
- VR 裁决引用:🟢 High — 直接读设计日志 VR 注册表
- 15+ 缺陷清单:🟡 Medium — 来自方案包组件 8 "实现期须修复的代码缺陷",未逐个独立验证,实现期可能发现细节差异
- 外部依赖(FCB45/CATZOC/Agder):⚫ Unknown — 标 EXTERNAL_CONFIRMATION_REQUIRED,本 Spec 主动避开

### 0.5 Codex 工程评审结论

**结论:有条件通过。** 6-Phase 主顺序合理,三项重点决策均可保留,但原稿存在若不修正就无法形成可验证 phase gate 的工程问题。本终稿已吸收以下修正,未推翻 VR/ALT/技术规约:

1. **P1 G3 证据去循环**:`RunManifest.algorithm_readiness_grade` 来自静态 capability catalog,不能反过来证明 G3。P1 必须先检查 raw trajectory/planner/event 证据,通过后才能提升 catalog grade。
2. **Rule 13 现状纠正**:当前 `classify_geometry` 不能正确识别两个标准追越场景;设计日志 R24 已记录其初始分类为 crossing/clear。P1 保留现有 15°/112.5° profile,但必须修复 OT_ing/OT_en 角色几何;Woerner αcrit 与锁定 FSM 仍留 P3。
3. **P1 安全门与 P2 oracle 解耦**:P1 用 truth center distance 与矩形外接圆半径和形成保守“不相交”充分条件;不把现有中心距 collision flag 当精确 oracle。P2 再上矩形 footprint 连续段检测,P3 上 C²A first-TOC。
4. **P1 可观察动作定量化**:使用版本化 `G3DisplayPredicate-v1`,不再把“明显转向”留到 P3 才定义。
5. **能力 API 修正**:能力契约入口是 `/api/capabilities`;`/api/algorithms` 仅返回 legacy integration dependency status,不是 capability matrix。P1 只扩展前者。
6. **Phase 依赖修正**:SeedTree 第五个 `disturbance` stream 是 P4 keyed CRN/统计前置条件,最小 SeedTree 扩展移到 P4;三模式 replay 仍在 P6。
7. **缺陷归属纠正**:“evaluator 5°/15° 偏差”和三套 CPA 统一属 P3;P1 真正阻塞项是 Rule 13 标准场景角色误分类。
8. **现状事实修正**:`RunSpec` 有 `seed` 字段和派生 `seeds` property;`ICOLAV` 完整抽象面还包括 `get_colav_data()`/`plot_results()`;速度合规须按每船 model bounds,不能把 Viknes 10 m/s 全局套到 multi-ship CSOG model。

---

## 1. 目标与范围

### 1.1 目标

复用上游 COLAV-Simulator(`ntnu-itk-autonomous-ship-lab/colav-simulator`),建立**动态 MPC 避碰 Playground**,使:

1. 现有 SB-MPC + VO 算法能跑通完整 COLREGs 场景(Rule 13/14/15 + multi-ship),达 G3 能力展示
2. 用户论文复现的 Custom MPC 能经统一 Adapter 接入,在全 COLREGs 场景被验证
3. 独立可信评价(C²A 安全 oracle + COLREG FSM + 三层分离)支持算法优化
4. canonical set + 统计套件支持 G4 基准验证与公平对比
5. subprocess 隔离支持 native crash 不杀主进程
6. 三模式重放 + 证据包 + 只读 Web 支持可复现与可视化

### 1.2 现状基线 (2026-07-28 审计)

| 维度 | 现状 | 来源 |
|---|---|---|
| 可用 MPC | 仅 SB-MPC | Algorithm-Capability-Matrix §2 |
| 可用非 MPC | 仅 VO | 同上 |
| G3 场景 | 仅 Rule 14-HO | §2 + §3.1 |
| PSB-MPC | G1(0.2s 短烟测,Eigen abort 退出码 134) | §2.1 |
| RRT | G1 未过(静态规划,非动态避碰) | §2.2 |
| RLMPC | G0(casadi/Acados 环境缺) | §2 |
| Custom MPC | 接口阶段(`module:factory -> ICOLAV` 已冻结) | §2 |
| 标准场景 | 5 个(head_on/crossing_give_way/crossing_stand_on/overtaking/overtaken)+ paper_ccta2023_multiship + 10 Imazu | §3 |
| 跨场景问题 | crossing 速度 15 m/s 超 Viknes [0,10] | `scenarios/crossing_give_way.yaml:csog_state` |
| 评价器 | 重建版(functional_reproduction,非论文数值复现) | `Design/Evaluator-Audit.md` |
| ICOLAV 接口 | 已含 plan()/reset()/get_current_plan()/get_diagnostics()/get_colav_data()/plot_results() | `core/colav/colav_interface.py:142` |
| PlanStatus | 六态齐(SUCCESS/TIMEOUT_FEASIBLE/INFEASIBLE/NUMERICAL_FAILURE/INVALID_INPUT/DEPENDENCY_UNAVAILABLE) | `core/colav/diagnostics.py:12` |
| PlannerTrace | 9+ 字段齐(9xN + selected_command + target_predictions + constraints + algorithm_details + schema_version 1.0) | 同上 :44 |
| RunSpec | 字段齐(strict_no_fallback/reproduction_level/algorithm_config/seed);`seeds` 是派生 property | `experiment/contracts.py:56` |
| SeedBundle | 4 streams(scenario/sensor/tracker/algorithm),缺 disturbance | 同上 :37 |
| RunManifest | 含 G0-G3 readiness grades + capability_profile_id + fallback_used | 同上 :111 |
| scenario_generator | ho/ot/cr bearing+course range + dist_between_ships + t_cpa/d_cpa threshold | `scenario_generator.py:50-66` |
| classify_geometry | 名义上 5 类(HO/OT/CR_GW/CR_SO/clear)+ Rule13/14/15 映射;阈值 15°/112.5°;两个标准 Rule13 场景初始角色误分类 | `evaluation/encounter.py:36` + 设计日志 R24 |
| stage_timeline | safety_distance ×8/×4 粗粒度,无 Woerner/Eriksen FSM | 同上 :69 |
| Web | `gui_server/main:app` FastAPI + `web_gui/` 静态;能力入口为 `/api/capabilities`;已展示 G1/G2/G3 分级 | `gui_server/main.py:556` + `web_gui/app.js:1548` |
| capabilities.py | 已有 readiness_grade 分级 + capability catalog | `experiment/capabilities.py` |
| 测试 | `39 passed, 1 skipped` | 方案包 R13 |

### 1.3 非目标

- 不在本项目重建完整 MASS-L3 TDL 三层系统(ALT-01 弃用)
- 不在算法未达 G3 时投入论文数值复现(VR-02)
- 不将 RRT 当动态避碰算法比较(ALT-03, RRT 不接收动态目标)
- 不将 legacy `guidance/custom_mpc_adapter.py` fallback 路径当 Custom MPC 正式接口(ALT-04)
- 不外推 FCB45 plant(VR-17);不依赖 Agder 地图 / metocean / 历史许可(标 EXTERNAL_CONFIRMATION_REQUIRED)

---

## 2. 完成等级定义 (沿用 Algorithm-Capability-Matrix §1)

| 等级 | 定义 | Web 展示 |
|---|---|---|
| G0 可发现 | 场景能解析,或依赖能 import | 否 |
| G1 短烟测 | 适配器构造并推进少量仿真步 | 否 |
| G2 完整闭环 | 代表场景从开始运行到终止,进程稳定,无 fallback | 可展示"能运行" |
| **G3 能力展示** | **相对 nominal 出现符合算法职责的可观察动作和诊断** | **可展示算法能力** |
| G4 基准验证 | 固定场景矩阵、多 seed、统一 Evaluator 和统计通过 | 可用于算法结论 |

**P1 全部出口要求 G3**(非 G4),按 `G3DisplayPredicate-v1` 判定:

1. 同一 scenario/seed/tracker/ENC 下先跑 nominal;nominal truth 最小中心距小于等于双方矩形 footprint 外接圆半径和(或已有 collision event),证明场景具有威胁性;
2. 被测算法 raw evidence 中 `requested==executed`,`fallback=false`,至少一次真实 solve,所有 solve plan 为 finite 9xN;
3. run 以 `time_limit` 或 `goal_reached` 正常结束;不得以 collision/grounding/failure 结束;
4. 对每个 active target,truth 最小中心距严格大于双方矩形 footprint 外接圆半径和
   `0.5*sqrt(L_os²+W_os²)+0.5*sqrt(L_ts²+W_ts²)`;这是 P1 保守充分条件,不是精确 collision oracle;
5. 在同一 sim clock 的公共采样时刻(必要时对 nominal 插值)比较,相对 nominal 出现可观察算法动作:`max |wrap(psi-psi_nominal)| >= 2°` 或 `max |U-U_nominal| >= 0.5 m/s`;
6. 对 CR_SO,P1 只能宣称“可观察动态避碰 G3”,不得宣称 Rule 17 profile compliance;Rule 17 三阶段判定在 P3。

`algorithm_readiness_grade=="G3"` 只是上述证据通过后的 catalog 投影,不属于证明输入。G3 不要求多 seed 统计(那是 G4,属 P4)。

---

## 3. 技术规约 (冻结,来自方案包组件 2)

### 3.1 坐标系

| 规约 | 内容 | 来源 |
|---|---|---|
| 全局 | WGS84/UTM zone 33N(EPSG:25833) | R17, R54 |
| 当地 | ENU 平面 xy | R3, R52 |
| 船体 | body x-forward/y-port | R22, R43 |
| 原点 | scenario-defined | R17 |
| 转换链 | WGS84→UTM(pyproj)→ENU→body(绕 chi) | R52 |

### 3.2 物理量单位

位置 m(ENU)/ 航向 rad(内部)deg(显示)/ 速度 m/s / 角速度 rad/s / 加速度 m/s² / 力 N / 距离 m / 时间 s / 船长宽吃水 m。

### 3.3 符号约定

| 符号 | 正向 | 零点 |
|---|---|---|
| chi/psi | 顺时针 from North | 0=正北 |
| r/ROT | 右转正 | — |
| β relative_bearing | target 相对 ownship,signed | ownship 艏向 |
| α contact_angle | ownship 相对 target = β+180° | target 艏向 |
| signed_tcpa | 负=CPA 已通过 | — |
| port/starboard | starboard=β∈(0,180) | — |

### 3.4 时序约定

时间戳 ROS2 steady / sim clock(Session 唯一)/ dt_sim 0.5s(canonical;V1 须为周期整数倍)/ solve 周期算法声明+RunSpec 可覆盖 / 首次 solve t=0(solve_id=1)/ horizon col-0=solve-time / hold 步保留原点 t_solve 按 t_now 采样 / phase 同 t: env→sensor→tracker→plan→control→积分。

### 3.5 数值边界

| 物理量 | 可行域 | 饱和/无效 |
|---|---|---|
| u(Viknes) | [0,10] m/s | 钳位 |
| ROT(Viknes) | [-15,15] deg/s | 钳位 |
| 正向力 | [0,13100] N | 钳位 |
| grid_size | (0,beam),beam=2.71m | ≥beam 坍缩 |
| horizon N | ≥1(G3 须完整) | N=1 仅 G2 |
| TCPA | signed(可负) | 负=post-CPA |
| cov eigenvalues | ≥-ε(PSD) | <-ε=INVALID_INPUT |
| 无效值 | NaN=故障/未扫描;-1=无效 | — |

### 3.6 接口语义

`9xN` plan shape≠(9,N)→NUMERICAL_FAILURE / selected_command 缺失→保持上一值 / solve_id hold 步不增 / Track age 超阈值→degraded / covariance 非 PSD→INVALID_INPUT / length/width 缺失→INVALID_INPUT。

---

## 4. 总体架构

### 4.1 主链(不变)

```
RunSpec → Session → Simulator → ICOLAV(CustomMPCAdapter) → 9xN plan → Evaluator → RunRecord
                                    ↑
                       typed PlannerInput + AlgorithmDescriptor
```

### 4.2 公共输出契约(冻结,VR-10)

`9xN` trajectory `[x,y,psi,u,v,r,x_ddot,y_ddot,psi_dot]`,col-0=solve-time。selected_command 单独。StateMapping 版本化。连续性检查。

### 4.3 VR 依赖图(决定 Phase 顺序)

```
VR-01..04 (主链/Adapter 角色) 
   ↓
VR-05..07 (场景/资格顺序)        ← P1
   ↓
VR-16,18 (sim clock/ENC)         ← P1
   ↓
VR-08..15 (Adapter/IO/调度/失败) ← P2
   ↓
VR-20..23 (评价三层/C²A/COLREG)  ← P3
   ↓
VR-19(SeedTree),24,25 (canonical/统计) ← P4
   ↓
VR-27..30 (Worker/probe/通信/映射) ← P5
   ↓
VR-19(replay),26,31 (重放/证据/Web) ← P6
```

VR-19 不被重裁决,只按依赖拆分工程落点:SeedTree 是 P4 CRN 的前置,三模式 replay 是 P6 交付。

---

## 5. 6-Phase 工程设计

### 5.1 Phase 切分总表

| Phase | 主交付 | 出口准则(全 G3 = 相对 nominal 可观察避碰动作+诊断) | 阻塞 VR | 优先级 |
|---|---|---|---|---|
| **P1 现有算法全场景 G3** | SB-MPC+VO 跑通 Rule13/14/15+multi-ship `G3DisplayPredicate-v1`;标准场景速度修复;Rule13 角色 bug 修复;generator 覆盖;Web capability 过滤 | VO/SB-MPC 在 HO/OT_ing/OT_en/CR_GW/CR_SO+multiship raw-evidence G3 | VR-05,06,07,16,18(部分)+ Rule13 阻塞缺陷 | **P0** |
| **P2 Custom MPC 接入** | CustomMPCAdapter(ICOLAV)+PlannerInput+AlgorithmDescriptor+多率调度+strict_no_fallback+矩形 footprint 连续段 collision boolean | 用户论文 MPC 经 Adapter 跑通全 COLREGs G3;collision 判定不再依赖中心距阈值 | VR-04,08,09,10,11,12,13,15+P2 阻塞缺陷 | **P0** |
| **P3 评价体系** | C²A CCD+COLREG FSM(Woerner/Eriksen)+三层分离+三套 CPA 统一+评价缺陷 | COLREG 评价可追溯;collision/grounding footprint+sweep;score 不抵消硬失败 | VR-20,21,22,23+评价缺陷 | **P1** |
| **P4 canonical+资格** | SeedTree 5 streams+canonical set(t=2 covering×3 seeds)+capability_dependencies hash+统计套件 | 至少一算法达 G4;promotion 人工+demotion 自动 | VR-19(SeedTree 部分),24,25 | **P2** |
| **P5 subprocess+probe** | subprocess 隔离+四 probe 准入+JSON Lines+版本化 TrajectoryMapping | native crash 不杀主进程;PSB/RLMPC 投影 9xN | VR-27,28,29,30 | **P2** |
| **P6 重放+证据+Web** | playback/exact/tolerance+六件证据包+只读 Web | artifact playback 可重跑;证据完整;Web 只读 | VR-19(replay 部分),26,31 | **P2** |

**避开外部依赖**:全程 nominal_reference plant、More_og_Romsdal ENC、God tracker(V1)。Agder/FCB45/metocean/历史许可标 EXTERNAL_CONFIRMATION_REQUIRED 不阻塞。

**P4/P5 边界**:P4 的首个 G4 只允许选择不会 native-abort 的 in-process 算法。PSB/RLMPC 等 native candidate 在 P5 worker isolation 通过前不得进入 P4 canonical 资格集;因此 P4→P5 顺序成立,但不代表 native candidate 已获 G4。

---

### 5.2 P1:现有算法全场景 G3

#### 5.2.1 P1.A 场景速度合规化

**问题**:`crossing_give_way`/`crossing_stand_on` 两船均为 15 m/s;`overtaking`/`overtaken` 至少一船为 15 m/s,超过这些标准场景所用 Viknes 上限 [0,10] m/s。`paper_ccta2023_multiship` 使用 KinematicCSOG(U_max=15 m/s),不能错误套用 Viknes 全局上限。

**工程**:
- 审计 5 个标准遭遇场景和 `paper_ccta2023_multiship` 的 `csog_state[2]` 与全部 `speed_plan`;
- 对每船从实际 model params 读取 `[U_min,U_max]`,YAML 中显式改成合规值;不得依赖积分器运行时钳位掩盖非法输入;
- 保持 own/target 速度相对关系(OT_ing ownship 更快;OT_en target 更快),并保证初始 signed TCPA 在 `(0,t_end)` 内;
- 不改 Viknes 物理模型(§3.5 边界冻结)
- 验证修后场景仍形成预期 encounter family,nominal truth 仍进入威胁状态

**验证**:`pytest tests/test_scenario_speed_compliance.py`(新建)——逐船断言 initial speed/speed_plan 落在对应 model bounds,OT 速度关系正确,signed TCPA 合法。

#### 5.2.2 P1.B Rule 13/15 evaluator 模板对齐

**问题**:`classify_geometry` 有 Rule13/14/15 family 映射,但现有 OT 条件使用 ownship-frame target bearing 与速度关系,两个标准追越场景初始状态实际落入 crossing/clear;所以原稿“现有阈值能正确分类”不成立。`stage_timeline` 仍仅为 safety×8/×4 粗粒度,无 Woerner/Eriksen FSM。

**P1 范围工程**(不动 Woerner αcrit 数值,那是 P3):
- 修复 P1 Rule13 标准角色几何:区分 ownship overtaking(OT_ing)与 ownship overtaken(OT_en),覆盖 target-frame/ownship-frame abaft-beam 关系;保持 P1 现有 15°/112.5° profile;
- 用标准场景内点验证 HO/OT_ing/OT_en/CR_GW/CR_SO;边界样本不在 P1 宣称 paper-profile 正确;
- `stage_timeline` 至少产生 post-CPA stage 3,只作为时序可观察诊断;
- Rule13/15 产出 raw-evidence 能力矩阵:nominal threat + VO/SB-MPC × God;Rule14 既有 God/KF 作为回归,不把新规则扩到 KF;
- **P3 才做**:Woerner αcrit_13=45°/αcrit_14=13°/αcrit_15=10° + Eriksen SF/OT/HO/GW/SO/EM FSM 阶段锁定 + Rule 17 三阶段

**评审结论(P1.B)**:不在 P1 切 Woerner αcrit 的 phase split **合理**,前提是:

1. 修复已确认的 Rule13 角色 bug,不能把它误称为“阈值 profile 问题”后推 P3;
2. P1 仅认证标准场景内点的动态避碰展示,artifact 标 `encounter_profile="legacy-g3-v1"`;
3. generator 边界样本、双变量 α/β profile、role lock、Rule17 合规结论全部留 P3。

否则 P1 会把错误角色写入 capability catalog,风险为阻塞级。

**验证**:
- `pytest tests/test_rule13_15_encounter_classification.py`
- `pytest tests/test_rule13_15_g3_matrix.py`——VO/SB-MPC × OT_ing/OT_en/CR_GW/CR_SO × God,按 `G3DisplayPredicate-v1` 断言 raw evidence,不读取 catalog grade 作为通过条件。

#### 5.2.3 P1.C scenario_generator 变化场景支持验证

**现状**:`scenario_generator.Config` 已有所需 range 字段。class defaults 中 `cr_bearing_range=[15.1,112.5]`,仓库 `config/scenario_generator.yaml` 当前运行值为 `[10.1,90.5]`;两者必须分开验证,不能混称同一配置。

**工程**:
- 对加载后的实际 Config 固定 seed 调 `generate_episode`,验证能产出 OT_ing/OT_en/CR_GW/CR_SO 各至少一个内点 witness;
- witness 必须速度合规,signed TCPA>0,DCPA≤配置阈值,且离 P1 分类边界有显式 guard band;
- 不用 class default 的存在代替实际 generation 证据;
- 边界/profile 冲突记录到 P3,不在 P1 改 Woerner 阈值。

**验证**:`pytest tests/test_scenario_generator_rule1315_coverage.py`(新建)。

#### 5.2.4 P1.D multi-ship G3 验证

**现状**:`paper_ccta2023_multiship` 已有(PSB 短烟测 0.2s 过,§2.1);VO/SB-MPC 未在此场景验证完整闭环。

**工程**:
- nominal/VO/SB-MPC 在 `paper_ccta2023_multiship` 跑到 `time_limit` 或 `goal_reached`;
- 逐帧从 truth 计算 ownship 对每个 active target 的最小中心距,不得依赖 reconstructed evaluator 是否完整输出所有 pair;
- VO/SB-MPC 按 `G3DisplayPredicate-v1` 通过;对至少一个 target 产生可观察动作;
- 不发明 multi-ship 优先级评价(VR-22,那是 P3);P1 只验证算法能跑、能避、有诊断

**验证**:`pytest tests/test_multiship_g3.py`;grade promotion 仅在 raw evidence PASS 后执行。

#### 5.2.5 P1.E Web 展厅按 capability 过滤

**现状**:`gui_server/main:app`(FastAPI)+ `web_gui/`(静态);截图确认已展示 G1/G2/G3 分级。

**工程**(按 Algorithm-Capability-Matrix §4):
- 续用现有 `/api/capabilities`,不新增重复 `/api/algorithms`;
- P1 显示 readiness_grade / supported_rules / supported_obstacles / supported_scenarios / verified_combinations / latest_evidence / known_failure;`role` 等完整 AlgorithmDescriptor 字段从 P2 开始;
- 场景选择按算法 capability 过滤(如 RRT 不显示动态避碰评分)
- 只有对应 raw evidence test PASS 的组合才能加入 `verified_combinations`;不得以算法全局 G3 自动叉乘所有场景;
- telemetry 继续展示 requested/executed/fallback

**验证**:`curl -s 'localhost:8010/api/capabilities?validation_rule_id=rule13'`(rule15/multiship 同理),并由 API test 验证跨规则/未认证组合被拒绝。

#### 5.2.6 P1 出口准则(可验证)

```bash
# 1. 场景速度合规
pytest tests/test_scenario_speed_compliance.py

# 2. Rule 13/15 几何分类
pytest tests/test_rule13_15_encounter_classification.py

# 3. Rule 13/15 G3 矩阵
pytest tests/test_rule13_15_g3_matrix.py

# 4. scenario_generator 覆盖
pytest tests/test_scenario_generator_rule1315_coverage.py

# 5. multi-ship G3
pytest tests/test_multiship_g3.py  # 新建

# 6. Web capability
pytest tests/test_p1_capability_api.py

# 7. 回归(不破坏 Rule 14)
pytest tests/test_rule14_planner_trace.py

# 8. P1 sim clock + ENC identity
pytest tests/test_p1_clock_enc_contract.py
```

**P1 sim clock/ENC 补门**:
- frame timestamp 严格单调,相邻差为 `dt_sim`;
- planner/event sim_time 均落在同一 session clock;
- 同比较 cell 的 ENC source 列表与 `enc_hash` 一致;
- P1 不实现 dense-output hold 插值,但不得伪造 solve_time。

**P1 出口定义**:以上 raw-evidence tests 全 PASS → 才更新 capability catalog → capability API tests PASS → 全量 `pytest` 无新失败。任一 VO/SB-MPC cell 未通过时,该 cell 保持原 grade,Phase P1 不得整体宣告完成。

---

### 5.3 P2:Custom MPC 接入

#### 5.3.1 P2.A CustomMPCAdapter(ICOLAV) 薄适配器(VR-08)

**现状**:legacy `guidance/custom_mpc_adapter.py:CustomMPCAdapter(IGuidance)` — 非 ICOLAV,有 2 latent bug,含 fallback 路径(ALT-04 弃用)。

**工程**:
- 新建 `core/colav/custom_mpc_adapter.py`,`class CustomMPCAdapter(ICOLAV)`,包装方案包 DP-04 冻结的接入点 `module:factory -> ICOLAV`
- 完整实现 ICOLAV 抽象面:`plan/reset/get_current_plan/get_diagnostics/get_colav_data/plot_results`;绘图方法允许 no-op,但不可缺失
- executed identity 可证:requested_algorithm = executed_algorithm,fallback=false(VR-13)
- **不复用** legacy `guidance/custom_mpc_adapter.py` 的 fallback 逻辑(ALT-04)
- legacy 文件标 `@deprecated` 不删(保留 ALT-04 弃用证据 + 供 paper 复现路径回溯)

**为何新建而非改 legacy**:legacy 是 `IGuidance` 适配器(不同抽象层),含静默 fallback(VR-13 strict_no_fallback 冲突)与 2 latent bug。改它 = 重写 + 破坏上游兼容(ALT-05 弃用理由)。新建 ICOLAV 适配器是 VR-08 裁决方案 A。

**评审结论(P2.A)**:路径选择**合理且优于改 legacy**。额外约束:
- legacy 只加 module/docstring deprecation marker,不让新 registry import 它;
- 删除/替换其中 hard-coded ecosystem path 不属于 P2 必须范围,除非它仍被生产入口 import;
- 正式 adapter 的 factory load、identity、异常映射必须各有 contract test。

#### 5.3.2 P2.B typed PlannerInput DTO(VR-09)

**现状**:`ICOLAV.plan()`(colav_interface.py:151)用位置参数(t/waypoints/speed_plan/ownship_state/do_list/enc/goal_state/w)。

**工程**:
- 新建 `PlannerInput`(frozen dataclass),由正式 adapter 在 `plan()` 边界从现有位置参数构造
- Adapter 验证:坐标(ENU)/ 单位(§3.2)/ Track age / covariance PSD / 9xN shape
- 缺失或无效 → INVALID_INPUT(VR-13);INVALID_INPUT 归因三源(坐标/单位/shape)
- 现有 `ICOLAV.plan()` 签名保持向后兼容;不强制 VO/SB-MPC 在 P2 改用 DTO,避免扩大 blast radius

#### 5.3.3 P2.C AlgorithmDescriptor(VR-11)

**现状**:`PlanDiagnostics`(`diagnostics.py:23`)有 requested/executed_algorithm 字符串,无完整 descriptor。

**工程**:
- 新建 `AlgorithmDescriptor` 12 强制字段(方案包 DP-11)+ `build_identity()` hash
- 静态冻结(配置)+ 动态绑 solve_id(运行时)
- `PlanDiagnostics` 扩展携带 `AlgorithmDescriptor`;config 漂移可追溯
- 12 字段清单(来自 DP-11):algorithm_id / version / role / supported_obstacles / solver_type / horizon_N / dt_solve / constraints / cost_components / fallback_policy / dependency_hash / schema_version

#### 5.3.4 P2.D 多率调度 + solve/hold 语义(VR-12)

**现状**:`VOWrapper`(colav_interface.py:246)有 `_solve_id`/`_planner_trace`,调度逻辑在 wrapper 内非统一。

**工程**:
- 提取统一调度层:solve 在 t=0(solve_id=1);hold 保留 horizon 原点 t_solve,按 t_now 采样
- 离线可关 deadline 标 `diagnostic_only`(VR-12)
- 防伪 solve_id / 错误重放:hold 步 solve_id 不增

#### 5.3.5 P2.E strict_no_fallback 六态分类(VR-13)

**现状**:`PlanStatus`(`diagnostics.py:12`)六态已含。`RunSpec.strict_no_fallback=True` 默认。

**工程**:
- 验证 `strict_no_fallback=True` 时无静默替代(fallback_used=false 强制)
- 六态分类完整:SUCCESS / TIMEOUT_FEASIBLE(可行但超 deadline,G3 soft 非 PASS,G4 fail)/ INFEASIBLE / NUMERICAL_FAILURE / INVALID_INPUT(归因三源)/ DEPENDENCY_UNAVAILABLE
- `DEPENDENCY_UNAVAILABLE` 在 run 层表示 `SKIPPED/NOT_EVALUATED`,必须持久化 manifest+failure evidence,不得记成算法数值失败或进入分数聚合;P2 实现明确的 manifest execution outcome,不只靠日志字符串

#### 5.3.6 P2.F 阻塞性缺陷修复(P2 部分)

来自方案包组件 8 "实现期须修复的代码缺陷",P2 阻塞部分(让评价基础可信):

| 缺陷 | P2 处理 | P3 完整 |
|---|---|---|
| 中心距碰撞 | 矩形 footprint 连续段相交 boolean | C²A first-TOC(R51) |
| 五边形 footprint | 改矩形 footprint | 同 |
| RK4 无 dense output | solve_ivp dense_output=True 或步内插值 | 同 |
| 三套 CPA 不一致 | 不在 P2 重复改 | P3 统一用 `encounter.cpa()` |

**评审结论(P2.F)**:P2 boolean / P3 first-TOC 的切分**合理**,但“只在 sim timestamp 离散采样矩形”精度不够。相对速度最高可令相邻样本跨过窄 footprint,产生 tunneling。P2 必须满足以下任一可证明条件:

1. 平移段对两矩形做 continuous swept-volume intersection;旋转段使用保守包络;或
2. 自适应 subdivision,保证每个 footprint corner 的相对位移不超过版本化 `ccd_step_tolerance_m`,并用测试证明高速垂直/对遇/旋转 case 不漏检。

P2 只需返回 collision boolean/interval;精确 first-TOC、同步 Conservative Advancement、容差收敛报告留 P3 C²A。这样保留 phase gate,又不以不可靠离散点冒充 footprint oracle。

#### 5.3.7 P2 出口准则

```bash
# Custom MPC Adapter(用户提供 module:factory)
pytest tests/test_custom_mpc_adapter.py  # 新建

# PlannerInput 验证
pytest tests/test_planner_input_validation.py  # 新建

# AlgorithmDescriptor
pytest tests/test_algorithm_descriptor.py  # 新建

# footprint continuous-segment collision(P2 boolean)
pytest tests/test_footprint_collision.py  # 新建

# 全 COLREGs G3(用户 MPC × HO/OT/CR_GW/CR_SO/multiship)
pytest tests/test_custom_mpc_g3_matrix.py  # 新建
```

**P2 出口定义**:用户论文 MPC 经 Adapter 在全 COLREGs 场景达 G3 + collision oracle 用 footprint。

**P2 entry criterion**:用户须提供可加载的 `module:factory`、依赖锁定信息、最小构造配置。若尚未提供,P2 只能完成 adapter conformance,不能宣告“用户论文 MPC 全场景 G3”出口通过。

---

### 5.4 P3:评价体系

#### 5.4.1 P3.A C²A CCD collision/grounding oracle(VR-21)

**算法**:Tang/Kim/Manocha ICRA 2009(R51)first-TOC。同步时间 Conservative Advancement。

**工程**:
- footprint(矩形 L×W)+ sweep(相邻步间轨迹);每船独立 hazards
- 三类 buffer 分离:safety domain / chart_geometric_clearance / operational UKC(V1 只声明 chart_geometric_clearance,VR-18)
- physical_collision = truth footprint 同步时间 CCD 相交(事实事件,不加 buffer)
- physical_grounding = truth footprint 与该船 hazards 相交(footprint+sweep)
- ENC 四类分离(DEPARE/UNSARE/M_QUAL/M_COVR)

#### 5.4.2 P3.B COLREG FSM(Woerner/Eriksen)(VR-22)

**来源**:
- Woerner 2016 PhD(R62):αcrit_13=45°/αcrit_14=13°/αcrit_15=10°(p.145 "all configurable... no prescribed value in COLREGS");port-to-port pose reward Eq.4.12 `R=[½(sin α+1)][½(sin β+1)]R_max`;Rule 17 in extremis Algorithm 11
- Eriksen 2020(R64):SF/OT/HO/GW/SO/EM state machine;entry/exit criteria with hysteresis Eq.9-15;EM entry `t_crit<t_crit^EM ∧ t_CPA>0` 仅从 GW/HO

**工程**:
- profile-parameterized:paper_compatible(αcrit Woerner)vs ship-length-scaled(Fujii/Namgung R59 椭圆船域)
- 锁定 FSM 不漂移(rule lock-on, all transitions to/from safe state)
- 双变量(β,α)+ 四阈值 + signed-sine pose + Rule 17 三阶段
- **不发明 multi-ship 优先级**(VR-22;multi-ship 评价留 EXTERNAL,不臆造)

#### 5.4.3 P3.C 三层评价分离(VR-20)

- 硬门(collision/grounding/fallback)/ 评分(CPA/maneuver/timely)/ 诊断(solve time/iterations/objective)
- score 不抵消硬失败
- reconstructed evaluator 定 evidence-flow stub(`Design/Evaluator-Audit.md` 已声明)
- gate 三态(PASS/SOFT/FAIL)+ qual 四态(G0/G1/G2/G3)

#### 5.4.4 P3.D 三套 CPA 统一

**现状**:`encounter.cpa()` / evaluator 内 CPA / live monitor CPA 三套。

**工程**:全部走 `encounter.cpa()`,signed TCPA(负=post-CPA);删除 P2/P3 双重归属,统一只在 P3 完成。

#### 5.4.5 P3.E 剩余缺陷(组件 8 P3 部分)

ENC 中心点距离→footprint+sweep / 删 Polygon interior / grunne 点喂 seabed / shore 折叠 UNSARE / bearing-only 分类 / range-only stage / evaluator 5°/15° profile 偏差 / Rule 17 FSM(与 P3.B 合并)/ grounding oracle 调不存在函数。KinematicShip legacy 参数误绑与 Acados wrapper 不可用移到 P5 对应 integration。

#### 5.4.6 P3 出口准则

```bash
pytest tests/test_c2a_collision_oracle.py  # 新建
pytest tests/test_colreg_fsm_woerner.py  # 新建
pytest tests/test_three_layer_evaluator.py  # 新建
pytest tests/test_unified_cpa.py  # 新建
# 全 COLREGs × VO/SB-MPC/Custom MPC,G3+ 可追溯评价
```

---

### 5.5 P4:canonical + 资格

#### 5.5.1 P4.A SeedTree 最小扩展(VR-19 部分)

- 在任何 CRN/statistical run 前,把现有 4 streams 扩为
  `run_seed → {scenario,sensor,tracker,disturbance,algorithm}`;
- stream key/version 写入 RunManifest;禁止依赖调用顺序;
- P4 只实现稳定 seed derivation 与 keyed disturbance injection;artifact/exact/tolerance replay 仍留 P6。

#### 5.5.2 P4.B canonical set(VR-24)

- t=2 covering array(NIST SP 800-142,R21)× 3 seeds × cells
- 本项目新建 regression set(非 PSB 全量,非经验拍 N)
- capability_dependencies hash:`[code,deps,scenario,enc,evaluator,tracker,plant,fingerprint]`

#### 5.5.3 P4.C 统计套件(VR-25)

- Wilson score CI(R76)/ Kaplan-Meier(R74)/ paired-t / Wilcoxon(R78)/ bootstrap(R77)
- CRN 仅外生(keyed CRN,解耦 call order);绝不插补(MNAR,R79)
- MNAR:crash missingness 由不稳定性驱动,不可丢弃/插补

#### 5.5.4 P4.D 资格门(VR-24)

- G4 = 固定矩阵 + 多 seed + 统一 Evaluator + 统计通过
- promotion 人工 + demotion 自动(capability_dependencies 任一变化失效)

#### 5.5.5 P4 出口准则

SeedTree 5 streams 可重现;至少一项无 native-abort 风险的算法达 G4;canonical set 可重跑;统计结论带 CI。native candidate 等 P5 isolation 后再进入资格集。

---

### 5.6 P5:subprocess Worker + probe

#### 5.6.1 P5.A subprocess Worker(VR-27)

- 每 run 新建 subprocess;reset 清空
- SIGTERM→SIGKILL;裁剪 geometry IPC;无网络/无写/CPU-mem 上限
- 解决 PSB Eigen abort(退出码 134,§2.1)杀主进程问题

#### 5.6.2 P5.B 四 probe 准入(VR-28)

- lockfile hash + build_identity;container digest;持久后置

#### 5.6.3 P5.C JSON Lines 通信(VR-29)

- framing;唯一 request_id 不重试;幂等缓存

#### 5.6.4 P5.D 版本化 TrajectoryMapping(VR-30)

- PSB(4,N)plant_prediction;RLMPC(6,N) r=psi_dot;method-driven;as-returned;PSB 无 INFEASIBLE
- DP-30 冲突解决:PSB `v:=0, method="native_assumption_course_aligned"`
- 在对应 worker/integration 内修复并测试 legacy KinematicShip 参数误绑、AcadosMPCWrapper dependency/constructor 不可用;不把这些与 P3 evaluator 缺陷混在一起

#### 5.6.5 P5 出口准则

native crash 不杀主进程;PSB/RLMPC 经 Worker 投影 9xN;container digest + lockfile hash 可验。

---

### 5.7 P6:重放 + 证据 + Web

#### 5.7.1 P6.A 三模式重放(VR-19)

- artifact playback(SeedTree 稳定路径)/ exact(bit-exact,native solver 跨 runtime 不保证)/ tolerance(runtime fingerprint,native 默认)
- 复用 P4 已落地的 5-stream SeedTree;P6 不再次改变 seed derivation

#### 5.7.2 P6.B 六件证据包(VR-26)

- 增量写 + 原子封存;列级 schema;大 horizon 拆文件;tamper_evident

#### 5.7.3 P6.C 只读 Web(VR-31)

- 版本化投影;additive-only;降采样推送;不发 raw;127.0.0.1;live seq+hash

#### 5.7.4 P6 出口准则

artifact playback 可重跑;native crash 证据完整;Web 只读不重算。

---

## 6. 数据流(端到端)

### 6.1 单次 run 相位(同 t 顺序,VR-16)

```
env(t) → sensor(t) → tracker(t) → plan(t) → control(t) → 积分→t+dt
                          ↑
                   ICOLAV.plan(PlannerInput)
                          ↓
                   PlannerTrace(solve_id, 9xN, ...)
                          ↓
                   RunManifest(capability_profile_id, readiness_grade)
                          ↓
                   Evaluator → EvaluatorResult
                          ↓
                   EvidenceWriter → RunRecord
```

### 6.2 多率调度(VR-12)

- solve 周期 = 算法声明(`AlgorithmDescriptor.dt_solve`)+ RunSpec 可覆盖
- 首次 solve t=0(solve_id=1)
- 非 solve 步 = hold:保留 horizon 原点 t_solve,按 t_now 采样,solve_id 不增
- 真实 solve 才写 PlannerTrace.events(VR-14)

### 6.3 失败传播(VR-13)

```
INVALID_INPUT → 归因三源(坐标/单位/shape)→ ColavExecutionError(status) → RunManifest.failure_status
TIMEOUT_FEASIBLE → G3 soft 非 PASS,G4 fail
INFEASIBLE/NUMERICAL_FAILURE → FAIL
DEPENDENCY_UNAVAILABLE → SKIP(不归失败,但记 diagnostic)
strict_no_fallback=True → 无静默替代,fallback_used=false 强制
```

`SKIP` 必须是 manifest 可机读 execution outcome,并映射 evaluator `NOT_EVALUATED`;不能只写 warning,也不能混入 collision/solver failure rate。

---

## 7. 错误处理

### 7.1 Planner 失败(六态,VR-13)

见 §5.3.5 + §6.3。

### 7.2 Worker 失败(P5,VR-27/29)

- SIGTERM 超时 → SIGKILL;唯一 request_id 不重试
- native abort(PSB Eigen)→ subprocess 死,主进程存活,记 DEPENDENCY_UNAVAILABLE

### 7.3 评价失败(P3,VR-20)

- 硬门失败(collision/grounding/fallback)→ gate=FAIL,score 不抵消
- 评价器异常 → evidence-flow stub 记录,reconstructed evaluator 不阻塞主链

### 7.4 持久化失败(P6,VR-26)

- 增量写失败 → 原子封存回滚;tamper_evident 检测

---

## 8. 测试策略

### 8.1 测试金字塔

- **单元**:PlannerInput 验证 / AlgorithmDescriptor hash / classify_geometry 四类 / cpa() signed / footprint 相交
- **集成**:单场景端到端(head_on × VO × God → RunRecord → EvaluatorResult)
- **矩阵**:G3 矩阵(P1/P2)/ canonical set(P4)
- **回归**:每 Phase 出口跑全量 `pytest`,不出现新失败

### 8.2 G3 验收标准(可观察动作+诊断)

P1 每场景 × 算法 × tracker 组合须由 raw truth/planner/events 先生成
`G3DisplayPredicate-v1` 结果:
- `requested_algorithm == executed_algorithm`
- `fallback_used == false`
- 至少一次真实 solve;solve plan finite 9xN
- 正常 `time_limit|goal_reached`,无 collision/grounding/failure event
- 每个 active target 的 truth 最小中心距 > 双方外接圆半径和
- 相对 nominal 航向变化≥2°或速度变化≥0.5 m/s
- scenario/seed/tracker/ENC hash 与 nominal 对照一致

上述 PASS 后才允许把对应 verified combination 与 grade 写入 capability catalog。P1 指标只证明 capability display,不等价于 P3 Woerner/Eriksen profile compliance。

### 8.3 测试清单(按 Phase)

| Phase | 新建测试 |
|---|---|
| P1 | test_scenario_speed_compliance / test_rule13_15_encounter_classification / test_rule13_15_g3_matrix / test_scenario_generator_rule1315_coverage / test_multiship_g3 / test_p1_capability_api / test_p1_clock_enc_contract |
| P2 | test_custom_mpc_adapter / test_planner_input_validation / test_algorithm_descriptor / test_footprint_collision / test_custom_mpc_g3_matrix |
| P3 | test_c2a_collision_oracle / test_colreg_fsm_woerner / test_three_layer_evaluator / test_unified_cpa |
| P4 | test_seed_tree / test_canonical_set / test_statistical_suite / test_capability_dependencies |
| P5 | test_subprocess_worker / test_four_probe / test_trajectory_mapping |
| P6 | test_replay_three_modes / test_evidence_package / test_web_readonly |

---

## 9. 缺陷分级(组件 8,15+ 项)

| 缺陷 | 级别 | Phase | 理由 |
|---|---|---|---|
| 中心距碰撞 | 阻塞-P2 | P2(连续段 boolean)/P3(C²A first-TOC) | collision oracle 基础可信 |
| 五边形 footprint | 阻塞-P2 | P2 | 同上 |
| RK4 无 dense output | 阻塞-P2 | P2 | hold 步采样精度 |
| 三套 CPA 不一致 | 阻塞-P3 | P3 | 评价一致性;P1 raw min-distance 不依赖 CPA score |
| Rule13 标准场景角色误分类 | 阻塞-P1 | P1 | OT_ing/OT_en 无法形成可信能力模板 |
| evaluator 5°/15° 偏差 | 阻塞-P3 | P3 | Woerner profile 的 detectable/substantial 阈值 |
| crossing 速度超限 | 阻塞-P1 | P1 | 场景合规 |
| catalog grade 被用作自身 G3 证明 | 阻塞-P1 | P1 | 循环验收,须改 raw evidence→promotion |
| verified_combinations 自动叉乘声明范围 | 阻塞-P1 | P1 | 可能展示未实际跑过的组合 |
| SeedBundle 缺 disturbance stream | 阻塞-P4 | P4 | keyed CRN/统计前置 |
| ENC 中心点距离 | 非阻塞 | P3 | footprint+sweep |
| 删 Polygon interior | 非阻塞 | P3 | ENC 几何正确 |
| grunne 点喂 seabed | 非阻塞 | P3 | grounding oracle |
| shore 折叠 UNSARE | 非阻塞 | P3 | ENC 几何 |
| bearing-only 分类 | 非阻塞 | P3 | 角色判定精度 |
| range-only stage | 非阻塞 | P3 | stage 精度 |
| Rule 17 FSM | 非阻塞 | P3 | COLREG FSM |
| KinematicShip 参数误绑 | 非阻塞 | P5 | PSB integration/worker mapping |
| AcadosMPCWrapper 不可用 | 非阻塞 | P5 | RLMPC 接入 |
| grounding oracle 调不存在函数 | 非阻塞 | P3 | grounding oracle |

**置信度**:🟡 Medium — 来自方案包组件 8,未逐个独立验证,实现期可能发现细节差异。

---

## 10. 避开的外部依赖

| 依赖 | 状态 | 规避策略 |
|---|---|---|
| FCB45 目标 plant | EXTERNAL_CONFIRMATION_REQUIRED | 用 nominal_reference,不外推(VR-17) |
| CATZOC 数值精度表 | EXTERNAL_CONFIRMATION_REQUIRED(IHO S-57 App2 Ch2 未取) | V1 只声明 chart_geometric_clearance,不做 operational UKC |
| 目标海域 metocean | EXTERNAL_CONFIRMATION_REQUIRED | V1 无风流(VR-06) |
| Agder 地图 | EXTERNAL_CONFIRMATION_REQUIRED(3600 episode 缺 Agder_utm33.gdb) | 用 More_og_Romsdal ENC(现有) |
| 历史许可 | EXTERNAL_CONFIRMATION_REQUIRED | 不依赖 |

---

## 11. 实施策略

**Approach A:严格 phase-gated**(用户已确认):
- 6 phase 顺序执行,每 phase 有 entry/exit criteria(基于 VR 依赖)
- P1 完成前不动 P2 代码
- 每 phase 干净基底,回归风险低
- P1 deliverable:VO/SB-MPC 全场景 G3;P2 deliverable:Custom MPC 全 COLREGs G3

**分支策略**(用户已确认):续用 `codex/colav-backend-algorithms`;后续 phase 如需派生,使用 `codex/` 前缀(如 `codex/mpc-p1-scenarios`)。

**评审门**:本 Spec 终稿须先获用户确认,之后才输出 P1 writing-plan 与执行代码。Spec 评审、P1 plan、P1 implementation 是三个独立交付门,不得自动串行越过。

---

## 12. 未决事项(实现期裁决,非 Spec 阻塞)

来自方案包组件 8 UNKNOWN:
- P2 `ccd_step_tolerance_m`/自适应细分上限
- route_exit 阈值
- HCI 证据
- maritime auto-promotion 标准
- PSB INFEASIBLE 区分

这些在对应 Phase 的 writing-plan 前裁决。P2 collision tolerance 未定不阻塞 P1,但会阻塞 P2 implementation;canonical `t=2 × 3 seeds` 已由 VR-24 冻结,不再列 UNKNOWN。

---

## 13. 与方案包的一致性核对

| 方案包组件 | 本 Spec 对应 |
|---|---|
| 组件 1 术语表 | §3 技术规约(引用,不重述) |
| 组件 2 技术规约 | §3(冻结,不改) |
| 组件 3 VR-01..31 | §4.3 依赖图 + §5 各 Phase |
| 组件 4 证据矩阵 | 不重述(见设计日志 R1..R79) |
| 组件 5 分解树 TD-01..04 | §5 各 Phase 覆盖 |
| 组件 6 ALT-01..18 | §1.3 非目标 + 各 Phase"为何不用 ALT-X" |
| 组件 7 场景 SC-01..10 | §5.2 P1 场景 + §5.3 P2 场景 |
| 组件 8 冲突/盲区 | §9 缺陷分级 + §10 外部依赖 + §12 未决 |

---

## 附录 A:VR-01..31 索引(速查)

| VR | DP | 裁决摘要 | Phase |
|---|---|---|---|
| VR-01 | 01 | 一条主链,不复制 TDL | 全局 |
| VR-02 | 02 | 论文复现后置 | P2 |
| VR-03 | 03 | RRT/VIM 可选插件 | 不阻塞 |
| VR-04 | 04 | Custom MPC 经统一 Adapter | P2 |
| VR-05 | 05 | V1 五类标准+PSB 小样本 | P1 |
| VR-06 | 06 | V1 四类双船 open-water+God+Viknes+无风流 | P1 |
| VR-07 | 07 | Nominal→VO/SB→Custom→PSB/RL 条件 | P1/P2 |
| VR-08 | 08 | CustomMPCAdapter(ICOLAV)薄适配器 | P2 |
| VR-09 | 09 | Adapter 验证坐标/单位/age/PSD/shape | P2 |
| VR-10 | 10 | 9xN col-0=solve-time;StateMapping 版本化 | P2 |
| VR-11 | 11 | AlgorithmDescriptor 12 字段+build_identity | P2 |
| VR-12 | 12 | 多率调度;solve t=0;hold 保留原点 | P2 |
| VR-13 | 13 | strict_no_fallback;六态;TIMEOUT_FEASIBLE | P2 |
| VR-14 | 14 | 真实 solve 写 events;9+4 字段 | P2 |
| VR-15 | 15 | 白盒+闭环同 Adapter;canonical Viknes | P2 |
| VR-16 | 16 | 统一 sim clock;三态 MeasurementScan | P1 |
| VR-17 | 17 | nominal_reference;多标签归因;不外推 FCB45 | P2 |
| VR-18 | 18 | 同 ENC+enc_hash;footprint+sweep | P1/P2/P3 |
| VR-19 | 19 | 三模式重放;SeedTree 5 streams | P4/P6 |
| VR-20 | 20 | 硬门/评分/诊断三层分离 | P3 |
| VR-21 | 21 | footprint+同步 CCD;三类 buffer 分离 | P3 |
| VR-22 | 22 | profile-parameterized FSM;Woerner αcrit | P3 |
| VR-23 | 23 | 任务/执行/求解三组指标 | P3 |
| VR-24 | 24 | canonical=t=2 covering×3 seeds;cap_dep hash | P4 |
| VR-25 | 25 | 不硬编码 seed;Wilson/KM/paired-t/Wilcoxon/bootstrap | P4 |
| VR-26 | 26 | 六件包;增量写+原子封存 | P6 |
| VR-27 | 27 | subprocess 优先;每 run 新建 | P5 |
| VR-28 | 28 | 四 probe 准入;lockfile+build_identity | P5 |
| VR-29 | 29 | JSON Lines;SIGTERM→SIGKILL | P5 |
| VR-30 | 30 | 版本化 Mapping;PSB v:=0 native_assumption | P5 |
| VR-31 | 31 | 版本化投影;additive-only;127.0.0.1 | P6 |

---

## 附录 B:Codex 工程评审记录

| 评审项 | 结论 | 必要修正 |
|---|---|---|
| P1.B 阈值策略 | **通过** | 不切 Woerner αcrit;但 Rule13 已知角色 bug 必须 P1 修,artifact 标 legacy-g3-v1,不得宣称 Rule17/profile compliance |
| P2.A 新 ICOLAV adapter 路径 | **通过** | 实现完整 ICOLAV 抽象面;legacy 只 deprecated,registry 不导入,不复制 fallback |
| P2.F footprint/C²A 切分 | **有条件通过** | P2 可只交 boolean,但必须连续段 sweep 或有误差界的自适应 subdivision;纯 timestamp 离散采样不通过 |
| 6-Phase 依赖 | **有条件通过** | SeedTree 5 streams 提前到 P4;native candidate 在 P5 前不得进 P4 资格集 |
| P1 出口准则 | **原稿不通过,本稿已修** | 去除 catalog-grade 循环证明,采用 raw-evidence `G3DisplayPredicate-v1` |
| 缺陷分级 | **原稿需修正,本稿已修** | Rule13 role bug→P1;evaluator 5°/15°与 CPA→P3;KinematicShip/Acados→P5 |
| 数据流/错误处理 | **有条件通过** | DEPENDENCY_UNAVAILABLE 必须可机读 SKIP/NOT_EVALUATED;P2 entry 依赖用户 factory |
| 测试策略 | **有条件通过** | direct evidence→promotion→API 三段门;multi-ship 从 raw truth 覆盖所有 active target |

**未发现需要“🔴 建议回炉 design-grounding”的新矛盾证据。** 修订均属工程依赖、现状事实、验收可判定性修正,未推翻 VR-01..31、ALT-01..18 或技术规约。
