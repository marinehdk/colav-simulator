# 方案包：动态 MPC 避碰 Playground

> **创建**: 2026-07-28
> **来源**: `docs/superpowers/design-logs/2026-07-27-dynamic-mpc-playground-design-log.md`（Step1-6 完整溯源）
> **状态**: 已交付 brainstorming
> **工作分支**: `codex/colav-backend-algorithms`
> **设计对象**: 复用上游 COLAV-Simulator，建立用于 Custom MPC 正确性、有效性和公平对比的动态避碰 Playground

---

## 方案包契约（brainstorming 权限边界）

- ✓ 可做：工程细节设计（架构/组件/数据流/错误处理/测试），已裁决方案内优化拔高。
- ✗ 不可做：推翻已裁决核心方案（VR-01..31），除非发现**新矛盾证据**（回炉 design-grounding）。
- ✗ 不可做：重提已弃用方案（ALT-01..18）。
- ✗ 不可做：擅自修改技术规约（单位/坐标系/符号），需改则回 design-grounding 重新裁决。

---

## 组件 1：术语表

| 术语 | 定义 | 本方案含义 | 边界（不是什么）| DP |
|---|---|---|---|---|
| Custom MPC | 用户自研 MPC | 经 `CustomMPCAdapter(ICOLAV)` 接入 | 非 legacy guidance adapter；非 SB/PSB/RL | 04,08 |
| `9xN` trajectory | `[x,y,psi,u,v,r,x_ddot,y_ddot,psi_dot]` | 公共输出契约；col-0=solve-time | 非 raw native state | 10,30 |
| physical_collision | truth footprint 同步时间 CCD 相交 | 事实事件，不加 buffer | 非中心距/CPA/safety domain | 21 |
| physical_grounding | truth footprint 与该船 hazards 相交 | 事实事件，footprint+sweep | 非中心点距离；非 operational UKC | 18,21 |
| chart_geometric_clearance | ENC 深度区间多边形 hazard 几何 clearance | V1 synthetic oracle | 非 operational UKC | 18,21 |
| C²A CCD | Conservative Advancement 连续碰撞检测 | 同步时间 first-TOC | 非端点采样；非独立 union 相交 | 21 |
| paper_compatible profile | 复现论文固定参数 | ccta_2023_demo + Woerner 角度 | 非法规硬事实；缩放不称复现 | 20,22 |
| ship-length-scaled profile | Fujii/Namgung 椭圆船域 | 独立风险指标 | 不替换 paper profile | 21,67 |
| G3 | 可观察能力+完整诊断+canonical 零硬门 | 组合证据 | 非全局算法等级；非 import | 24 |
| canonical set | t=2 covering×3 seeds×cells | 本项目新建 regression set | 非 PSB 全量；非经验拍 N | 24 |
| SeedTree | 稳定路径派生独立 RNG 流 | `run_seed → {scenario,sensor,tracker,disturbance,algorithm}` | 非单一根 seed；非全局 RNG | 19 |
| keyed CRN | 稳定 key 生成外生 draw 的 CRN | 解耦 call order | 不同步 measurement stream | 19,25 |
| capability_dependencies | claim 依赖的 hash 聚合 | `[code,deps,scenario,enc,evaluator,tracker,plant,fingerprint]` | 非备注；任一变化失效 | 24 |
| MNAR | Missing Not At Random | crash missingness 由不稳定性驱动 | 非 MCAR；不可丢弃/插补 | 25,89 |
| TIMEOUT_FEASIBLE | 可行解但超 deadline | G3 soft 非 PASS；G4 fail | 非 SUCCESS；非 hold | 13,82 |
| TrajectoryMapping | 版本化 native→public 映射 | PSB 4D→9D / RLMPC 6D→9D | 非 vstack zeros；非重生成 | 30 |
| native_assumption_course_aligned | PSB 假设 v≡0 | `v:=0, estimated=false` | 非遗漏；非 sin(chi) | 30 |

---

## 组件 2：技术规约表

### 坐标系

| 规约 | 内容 | 来源 |
|---|---|---|
| 全局 | WGS84/UTM zone 33N（EPSG:25833） | [R17][R54] |
| 当地 | ENU 平面 xy | [R3][R52] |
| 船体 | body x-forward/y-port | [R22][R43] |
| 原点 | scenario-defined | [R17] |
| 转换链 | WGS84→UTM(pyproj)→ENU→body(绕 chi) | [R52] |

### 物理量单位

| 物理量 | 单位 |
|---|---|
| 位置 x,y | m（ENU） |
| 航向 psi/chi | rad（内部）/ deg（显示） |
| 速度 u,v,U | m/s |
| 角速度 r | rad/s |
| 加速度 | m/s² |
| 力 Fx,Fy | N |
| 距离/clearance | m |
| 时间 | s（性能 ms） |
| 船长/宽/吃水 | m |

### 符号约定

| 符号 | 正向 | 零点 |
|---|---|---|
| chi/psi | 顺时针 from North | 0=正北 |
| r/ROT | 右转正 | — |
| β relative_bearing | target 相对 ownship，signed | ownship 艏向 |
| α contact_angle | ownship 相对 target = β+180° | target 艏向 |
| signed_tcpa | 负=CPA 已通过 | — |
| port/starboard | starboard=β∈(0,180) | — |

### 时序约定

| 规约 | 内容 |
|---|---|
| 时间戳 | ROS2 steady / sim clock（Session 唯一） |
| dt_sim | 0.5s（canonical）；V1 须为周期整数倍 |
| solve 周期 | 算法声明 + RunSpec 可覆盖 |
| 首次 solve | t=0（solve_id=1） |
| horizon col-0 | solve-time 当前状态 |
| hold 步 | 保留原点 t_solve，按 t_now 采样 |
| phase | 同 t: env→sensor→tracker→plan→control→积分 |

### 数值边界

| 物理量 | 可行域 | 饱和/无效 |
|---|---|---|
| u（Viknes） | [0,10] m/s | 钳位 |
| ROT（Viknes） | [-15,15] deg/s | 钳位 |
| 正向力 | [0,13100] N | 钳位 |
| grid_size | (0,beam)，beam=2.71m | ≥beam 坍缩 |
| horizon N | ≥1（G3 须完整） | N=1 仅 G2 |
| TCPA | signed（可负） | 负=post-CPA |
| cov eigenvalues | ≥-ε（PSD） | <-ε=INVALID_INPUT |
| 无效值 | NaN=故障/未扫描；-1=无效 | — |

### 接口语义

| 字段 | 缺失/无效处理 |
|---|---|
| `9xN` plan | shape≠(9,N)→NUMERICAL_FAILURE |
| selected_command | 缺失→保持上一值 |
| solve_id | hold 步不增 |
| Track age | 超阈值→degraded |
| covariance | 非 PSD→INVALID_INPUT |
| length/width | 缺失→INVALID_INPUT |

---

## 组件 3：决策卡片集（VR-01..31）

详见设计日志 Step4 + Step5。核心裁决：

| VR | DP | 裁决 |
|---|---|---|
| VR-01..04 | 01..04 | 一条主链；Custom MPC 经统一 Adapter；论文/RRT/VIM 条件插件 |
| VR-05..11 | 05..11 | 五类标准场景+PSB 小样本；V1 四类双船；typed PlannerInput+AlgorithmDescriptor |
| VR-12..18 | 12..18 | 多率调度；strict_no_fallback；统一 sim clock；footprint+sweep |
| VR-19..26 | 19..26 | 三模式重放；三层评价；C²A 安全 oracle；profile COLREG；组合资格；正确统计 |
| VR-27..31 | 27..31 | subprocess Worker；四 probe；JSON Lines；版本化 Mapping；Web 只读 |

**Step5 DESIGN-IT-TWICE 确认**（7 项）：DP-08/19/21/22/24/25/30 全部采纳方案 A。DP-30 `v` 冲突解决：`v:=0, method="native_assumption_course_aligned"`。

---

## 组件 4：证据矩阵

详见设计日志 0.4 节 [R1..R79]。共 79 条：DOMAIN_EVIDENCE ~45 + PROJECT_FACT ~30 + DOCUMENTED_INTENT ~4。三类置信度（检索/权威/适用）分列。

---

## 组件 5：技术分解完整树

| TD | 技术 | 子模块（→DP） | 状态 |
|---|---|---|---|
| TD-01 | Custom MPC 插件契约 | 输入(09)、输出(10)、声明(11)、生命周期(12)、失败(13)、诊断(14) | ✓ 闭环 |
| TD-02 | 最小闭环仿真夹具 | 相位(16)、失配(17)、环境(18)、重放(19) | ✓ 闭环 |
| TD-03 | 独立评价与资格 | 安全(21)、COLREG(22)、任务(23)、能力门(24)、统计(25)、证据包(26) | ✓ 闭环 |
| TD-04 | 外部算法 Worker | 隔离(28)、通信(29)、归一化(30) | ✓ 闭环 |

无 DECOMPOSITION_INCOMPLETE。

---

## 组件 6：弃用方案及理由

详见设计日志 0.7 节 ALT-01..18。核心：

- ALT-01..04：重建完整 TDL / 三链同优先 / RRT 当动态算法 / legacy adapter 当正式接口
- ALT-05..06：DP-08 新独立接口 / hybrid fast-path
- ALT-07..08：DP-21 自适应细分 / 简化线性上界
- ALT-09..10：DP-22 Eriksen 宽角度 / Murray 简化
- ALT-11..12：DP-24 全量 PSB / 经验拍 N
- ALT-13..14：DP-30 注入虚拟 sway / PSB 不映射
- ALT-15..16：DP-19 单一 file-hash / 全 exact
- ALT-17..18：DP-25 固定 30+Wald / 纯描述性

---

## 组件 7：需求场景 + 验收边界

| SC | 场景 | 验收 |
|---|---|---|
| SC-01 | Custom MPC 白盒固定输入 | 预测/约束/代价/状态/耗时可查 |
| SC-02..06 | Rule 14/15-16/15-17/13/multi-ship | 正确角色+及时动作+安全通过 |
| SC-07 | ENC 受限水域 | 不搁浅/越界换净空 |
| SC-08 | deadline/不可行/crash | 结构化失败+服务存活 |
| SC-09 | 论文结果比对 | G3 后启用+冻结 profile |
| SC-10 | PSB episode 迁移 | raw/normalized/migration 三件套 |

---

## 组件 8：已知冲突与未闭环盲区

**冲突（已解决）**：DP-30 PSB `v` → `v:=0, method="native_assumption_course_aligned"`。

**EXTERNAL_CONFIRMATION_REQUIRED**：FCB45 目标 plant / CATZOC 数值精度表 / 目标海域 metocean / Agder 地图 / 历史许可。

**UNKNOWN（实现期裁决）**：具体容差数值（grid_size/细分）/ route_exit 阈值 / canonical t-way·seed 数 / HCI 证据 / maritime auto-promotion 标准 / PSB INFEASIBLE 区分。

**实现期须修复的代码缺陷**（15+）：中心距碰撞 / 五边形 footprint / RK4 无 dense output / 三套 CPA 不一致 / ENC 中心点距离 / 删 Polygon interior / grunne 点喂 seabed / shore 折叠 UNSARE / bearing-only 分类 / range-only stage / evaluator 5°/15° 偏差 / 无 Rule 17 FSM / KinematicShip 参数误绑 / AcadosMPCWrapper 不可用 / grounding oracle 调不存在函数。

---

## 移交 brainstorming

本方案的核心技术决策已通过 design-grounding 裁决。brainstorming 负责工程细节设计，不得推翻已裁决方案/重提弃用方案/修改技术规约，除非发现新矛盾证据则回炉 design-grounding。
