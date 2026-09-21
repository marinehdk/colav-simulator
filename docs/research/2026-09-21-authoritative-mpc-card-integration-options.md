# Authoritative MPC 卡片（2026-09-21）集成方向调研

日期：2026-09-21。对象：同事 qiao 的 L4/L5 MPC 源码（冻结快照 `~/Code/external_sources/qiao_gnc_sources_20260920`，Git `67a857e`，快照校验 PASS）如何成为可执行 GNC Stack 卡片。**方向已确认（方案 B）并已实施，见文末实施记录。**

## 1. 结论先行

**推荐方案 B（混合卡）：保留现有 Authoritative GNC 卡的全部 guidance/分配/船模/环境链（GNC 仓 0bbce06），仅把 PID `ship_control_node` 替换为 qiao 的 MPC 控制节点（外部参考模式），新建独立卡片 "Authoritative MPC · 2026-09-21"。**

核心理由（证据见第 3 节）：

1. **接口逐字对齐**：qiao MPC 节点订阅集是现 PID 控制器的超集，四个核心话题（`/ship/odometry`、`/target_pose`、`/control/heading_setpoint`、`/control/speed_setpoint`）与 PID 节点完全同名，输出同为 `/cmd_tau`，类名同为 `ShipControllerNode`。
2. **三个规划器零改动可用**：VO/Fan-MPC 走 VelocityIntent（G7）、Mid-MPC 走定时轨迹合同（G5），两者都在现 guidance 链；换控制器不动这些合同，`plan_bridge` 原样复用。
3. **同一艘船**：MPC 配置的模型参数与现卡 plant（44.1 m A4000）量级一致（mass_x 242 t = plant 220 t + added 22 t；mass_y 380 t = 220 t + 160 t；damping_x 3500 相同）。
4. **干净 A/B**：与 PID 卡同 guidance、同分配、同船模、同环境，唯一变量是控制器——正是卡片体系（`frozen_original_source_port` + 独立验收）的设计用途。

方案 A（qiao 全栈独立卡）技术上可行但成本高且 planner 兼容性差（第 4 节）；方案 C（约束融入 Mid-MPC）不产出卡片，属另一工作流（第 5 节）。

## 2. 两套栈的血缘与分叉量化

qiao 快照与现有 Authoritative GNC 卡同源（同一产品线），但 guidance 已大幅分叉：

| 文件 | qiao 行数 | GNC 现版(0bbce06) 行数 | qiao vs 原版(e1d435d) 差异行 | qiao vs 现版差异行 |
|---|---:|---:|---:|---:|
| `ship_guidance_node.cpp` | 5333 | 6551 | ~11577 | ~11884 |
| `active_route_manager_node.cpp` | 623 | 1545 | ~801 | ~1032 |
| `coordinate_transform_node.cpp` | 1358 | 1440 | ~244 | ~388 |
| `thrust_allocation_node.cpp` | 1899 | 2031 | ~238 | — |

- qiao 的 guidance 分支**不含** G1-G7 任何一项：无普通/紧急避碰模式分离（G1）、无逐点限速+减速传播（G2）、无 `planner_trajectory_v1` 定时轨迹合同（G5）、无 VelocityIntent 接口（G7）。其 `RoutePlan.msg`/`AvoidancePlan.msg` 缺 `route_revision`、`trajectory_*`、`parent_route_revision` 字段。
- qiao 的 L5 是现链 L5 的**旧代祖先**：缺 propeller_curve_shadow 诊断、cruise 主推对称 canary、`evaluate_allocation` 抽象（现链独有，见 `thrust_allocation_node.cpp` diff）。现链 L5 已发布 MPC 需要的全部反馈：`achieved_tau`、`residual_tau`、`allocation_status`、`rudder_effectiveness`。
- 快照**不含** ship_dynamics / env_engines（原 GNC 183 文件快照有）；L4 MPC 自带预测模型（`four_dof_vessel_model.hpp` 291 行、`current_vessel_model.hpp`、`actuator_realization_model.hpp` 422 行）。
- L2（`l2_planning/`，20 文件 Python）是 ENC 航线规划，与卡片无关（Simulator 提供场景与航线），不纳入本卡。

## 3. qiao L4 MPC 节点事实（集成面）

来源：`l4_control/mpc_control_20260728/src/ship_control_node.cpp`（2906 行）+ 7 个 hpp。

- **接口**（`ship_control_node.cpp:71-114`）：订阅 odometry/Path(`/ship/waypoints`)/RoutePlan(`route_plan_topic` 默认 `/gnc/active_route`)/target_pose/heading_setpoint/speed_setpoint/env(`/env/total_load`)/achieved_tau/residual_tau/allocation_status/rudder_effectiveness；发布 `/cmd_tau` + debug。无服务端。
- **双模式开关** `mpc.integrated_guidance_enable`（`:210`，`:447`，`:903`）：`true` 时内嵌制导拥有路线跟踪（注释原文 "MPC owns route engagement; no external guidance/PID node is required"）；`false` 时走外部 `/control/heading_setpoint` + `/control/speed_setpoint` 参考——与 PID 节点同构。
- **求解器**：`solve_mpc_2state`（`:2034` 起）有限时域 Riccati 递推 + 控制饱和；非 IPOPT/acados（INTEGRATION_BOUNDARIES.md 结论，勿称非线性 MPC）。求解预算 `max_solve_time_ms: 100`，控制周期 0.1 s，预测 120 s / 控制 20 s / 模型步长 0.5 s。
- **配置船型**（`config/mpc_control_20260728.yaml`）：45 m 级 vessel；max_force_x 405 kN / max_torque_z 420 kN·m（DP 960）；cruise 6.8 m/s。模型参数与现卡 A4000 plant 一致（第 1 节理由 3）。
- **包名**：`mpc_control_20260728`，可执行 `mpc_control_20260728_node`；但 include 前缀为 `ship_control/`——与现 PID 包同名冲突，合入 GNC 仓分支时需处理（重命名前缀或提取期隔离）。
- **快照缺口**：其 CMake 引用的 7 个包内测试（`test_*`）源码被冻结规则排除，不可直接复跑；卡片验收需自建聚焦测试。

## 4. 方案对比

| 维度 | A：qiao 全栈独立卡 | **B：混合卡（推荐）** | C：约束融入 Mid-MPC |
|---|---|---|---|
| 组成 | qiao guidance(分叉旧支) + MPC(内嵌制导) + qiao L5 + 现 plant | 现链 0bbce06 guidance/L5/plant + MPC(外部参考模式) | Mid-MPC 优化器内加分配/执行器约束 |
| VO | 需新桥接（无 VelocityIntent 合同；语义降级为 operator 指令或空间航线） | **零改动**（现 plan_bridge → G7） | 不适用 |
| Fan-MPC | 同上 | **零改动**（现 plan_bridge → G7） | 不适用 |
| Mid-MPC | 定时轨迹退化为空间航点+限速（丢时间/身份/有效期合同，即丢 G5 成果） | **零改动**（现 plan_bridge → G5） | 本体 |
| 行为保真 | 接近 qiao 远端系统 | 只检验"同参考下 MPC vs PID 跟踪器"，不含其内嵌制导 | 改变 Mid 本体行为 |
| 工程量 | 大：guidance 缺 G1-G7 六轮修复 + 11k 行分叉，planner 桥接全新 | 中：GNC 分支加包 + 新构建 lane + 卡片目录/参数 | 大：决策变量/动力学一致性需证明 |
| 风险 | 已修故障复发（VO 0.625 m/s 限速污染、OT 失败类）+ 未测组合 | MPC 外部参考模式未经同事实测（其配置运行内嵌模式） | Mid-MPC 回归面大 |
| 可回退 | 独立卡可回退 | PID 卡不动，独立 lane 可回退 | Mid-MPC 本体变更 |

B 的诚实边界（必须向用户明示）：该卡回答"**同一 guidance 参考下，qiao MPC 控制器与原 PID 控制器的闭环差异**"，不回答"qiao 远端完整系统行为复现"。后者是 A 的价值；若目标是复现远端行为，A 值得做但应作为后续第二变体，先以 B 落地卡片能力。

## 5. 方案 B 实施概要（方向确认后执行）

1. **GNC 仓集成分支**：从冻结快照引入 `mpc_control_20260728` 包（provenance commit 记录来源 Git `67a857e`）；处理 `ship_control/` include 前缀冲突；不触碰现 PID 包。
2. **新构建 lane**：`extract_native.py` NODES 表加 MPC 节点条目；新 SOURCE_MANIFEST + 审批哈希 + `build/original_mpc-current`；复用 native ABI shim 与显式时钟调度。
3. **Simulator 侧**：新增 `authoritative_mpc` 卡片目录（sibling of `original_gnc`，复用 adapter/stack/plan_bridge/observers/qualification 机制）；`modular_gnc/catalog.py:1041` 旁注册新卡；MPC 节点参数从其 yaml 转入新 `baseline.json`（带 provenance，不静默调参）；`mpc.integrated_guidance_enable=false`。
4. **验收标准（草案）**：
   - 构建：lane manifest 哈希钉死，native 库加载，extraction 含 MPC 节点。
   - 聚焦测试：MPC 外部参考模式跟踪（heading/speed 阶跃）、terminal stop、tau 限幅/速率约束、分配反馈消费。
   - 场景：VO / Fan-MPC / Mid-MPC 三算法 × OT/HO/CS（或既有五场景）headless 到达、无碰撞、归线；与 PID 卡同 seed 对照报告。
   - 卡片 API：`available=true`，`/api/gnc/stacks` 出现 "Authoritative MPC · 2026-09-21"。

## 6. 未覆盖与遗留

- MPC 求解 100 ms 预算在仿真加速（>1x）下的确定性表现未测，需在聚焦测试中定义阈值。
- qiao 快照的 L2 规划、sensor_fusion、safety_supervisor 未纳入（卡片不需要；若后续做 L2 卡片另立项）。
- 方案 C 的约束清单（`allocation_aware_constraints.hpp` 137 行、`actuator_realization_model.hpp`、rate limits、terminal_stop_policy）已在快照中定位，若用户要并行推进 Mid-MPC 融合可另出调研，但与本卡互不阻塞。

## 7. 实施记录（2026-09-21，方案 B 已落地）

### 7.1 GNC 仓（独立 worktree，不碰 PID lane 主检出）

- Worktree `~/Code/GNC-mpc-lane`，分支 `feat/mpc-control-lane`，提交 `d917ed9`：从冻结快照字节级导入 `src/gnc/mpc_control/`（12 文件，含 CMakeLists/package.xml 原样保留 provenance；快照 SHA256SUMS 校验 10/10 代码文件 + 2 打包文件 diff 一致）。
- `SOURCE_MANIFEST.csv` 重建：200 行（原 188 + 12），lane 审批哈希 `f7ee193e04b5165444a680b1e774e8b730639aa13dfd9f013face25ee5cc8a8d`。
- PID lane 主检出 `~/Code/GNC`（main @ 0bbce06）未动。

### 7.2 构建 lane（Simulator 仓工具参数化，默认行为不变）

- `tools/original_gnc/extract_native.py`：`module_table(controller_package)` 覆盖钩子 + `--controller-package` / `--source-manifest-sha256`；MPC lane 将 `ship_control_node` 模块指向 `gnc/mpc_control`（类名同为 `ShipControllerNode`，`{module}.hpp` 保留规则天然命中）。
- `tools/original_gnc/state_fields.py`：新增 `ship_control_node_mpc` snapshot（PID 同名状态字段 + tau_last/tau_filtered/target/mpc 接合面；无 quiet_zone/dp_deadband——该节点不存在这两个字段）。
- `tools/original_gnc/build_native.py`：`write_bindings` snapshot 覆盖 + lane 参数透传 + 构建清单记录 `controller_package`。
- 构建产物 `build/original_mpc-20260921-v3-frozen/`（符号链 `original_mpc-current`）：库 SHA-256 `61e66427174831ff309c201c14361a010aead91f68474aa707237767bdb44b4c`；提取 9 个 MPC 文件、12 回调、control_loop 定时 100 ms。v1 为同源首建（库 `fdb7e8fb…`），v2 为已 revert 的实验补丁构建（保留作证据）。
- `colav_simulator/original_gnc/native.py` `verify_build`/`NativeModule`、`policy.py`、`observers.py`、`stack.py` 增加 `approved_manifest_sha256` 透传（默认仍为 PID lane 常量）。

### 7.3 Simulator 卡片

- 新包 `colav_simulator/authoritative_mpc/`：`configuration.py`（`AuthoritativeMpcConfig`，env `COLAV_AUTHORITATIVE_MPC_SOURCE/BUILD`，默认 `~/Code/GNC-mpc-lane` + `build/original_mpc-current`；stack id `authoritative-mpc-20260921-v1-env-{off,on}`）、`catalog.py`（卡片 "Authoritative MPC · 2026-09-21"）、`data/baseline.json`。
- baseline 参数：10 节点中 9 个与 PID 卡逐字节同源同参数；`ship_control_node` 为 MPC 节点 179 参数（kernel describe 全集 + qiao yaml 102 项观测值覆盖；`mpc.integrated_guidance_enable=false` 卡片合同；yaml 中 2 个未声明死键 `mpc.turn_anticipation_distance_m`/`turn_exit_distance_m` 记录在 evidence 不入 baseline）。
- response_approximation 两份：借用 PID lane 同 guidance 闭环测量常数作 planner 初值，**删除全部 trajectory_r_squared 证据字段**——`qualification.evaluate` 据实判 UNQUALIFIED，runs 自动 diagnostic-only，直至本 lane 自有测量（诚实边界：控制器不同，PID 闭环资格不可冒充）。
- 分发接线：`core/ship.py`（Config.authoritative_mpc 字段 + from_dict/to_dict/build_ship 分支与互斥校验）、`experiment/runner.py`（backend_kind=authoritative_mpc 绑定分支）、`modular_gnc/catalog.py`（MPC 条目并入 `original_gnc_stacks`、preset 并入 `product_presets`）、`original_gnc/adapter.py`（backend_kind/manifest 哈希改由 config 属性驱动，`from_config` 双后端，运行时指纹覆盖新包）。
- UI 零改动：`config-shell.js` 通用渲染 `product_presets`，新卡自动出现。

### 7.4 验证

- 聚焦测试 `tests/test_authoritative_mpc_controller.py` 9/9：构建 lane 身份、外部参考模式合同、guidance 参考→MPC 有限有界 tau→船舶前进（HEADING_SPEED_AUTOPILOT）、分配反馈（achieved/residual tau + env total）接线、**Mid 定时轨迹合同（planner_trajectory_v1）在 MPC lane 上照常接纳**、卡片目录/identity 钉子。
- 回归：`-k "original_gnc or authoritative_mpc"` 146 通过；catalog/ship wiring 60 通过；PID 卡产品钉子测试按新增卡片事实更新（full stack 哈希不变）。改动文件 ruff 全绿（仓库其余 53 个预存 lint 错误在无关文件，未触碰）。

### 7.5 外部参考模式失稳根因与修复（关键发现）

初版验收中 Fan-MPC×MPC 卡在 CS 场景 1330s 报 footprint 不可行（PID 卡同 seed 325s 完成）；L 形航线探针证实：**MPC 外部参考模式下转弯后艏向持续 20–90° 极限环振荡不收敛**（PID 卡同工况误差 <1°）。

排查记录（证据均在 `runs/diag/`）：排除 yaw 符号约定（cruise/dp=0 回退 1.0 正确）、模型惯量失配（ndo.mass_yaw 36.5e6 = plant Izz 27e6 + N_dot_r 9.5e6 精确一致）、plant soft yaw 弹簧（0.3 rad/s 正常航行不可达）、heading setpoint 阶跃（试打源码级 rate-limit 补丁无效后已 revert，lane 回到纯冻结源码）、input_delay（下调仅部分改善 RMS 49→18°）。参数扫描命中：**`mpc.torque_rate_limit_z_nm_s = 250000`**——0.1s 控制拍下每拍仅许 25 kN·m 力矩变化，2 状态 Riccati 的艏摇修正被速率饥饿 → 闭环相位滞后 → 极限环。放开后（保持其余全部冻结值）L 形探针后段 RMS **0.12°**（冻结值 49.3°）。

修复落在 lane baseline（非源码）：`mpc.torque_rate_limit_z_nm_s 250000 → 1e7`，理由与测量证据记入 `baseline.json` 的 `evidence.ship_control_node.lane_parameter_overrides`。GNC 分支最终为纯冻结源码（import d917ed9 + 两个 revert 9eab996/2f0bf3d，manifest 哈希不变 f7ee193e…）。诊断工具：`runs/diag/mpc_heading_response_probe.py`（L 形航线双卡对照）、`runs/diag/mpc_param_sweep.py`（8 组参数扫描）。

### 7.6 场景验收（2026-09-21，seed 0，CS/rule15，t_end 1500s）

| 卡片 | VO | Fan-MPC | Mid-MPC |
|---|---|---|---|
| **Authoritative MPC · 2026-09-21** | COMPLETE，最小距离 239.9 m，0 碰撞 | COMPLETE，316.5 m，0 碰撞 | COMPLETE，431.0 m，0 碰撞 |
| Authoritative GNC · 2026-09-14（PID 对照） | COMPLETE，186.8 m，0 碰撞 | COMPLETE，314.9 m，0 碰撞 | COMPLETE，422.9 m，0 碰撞 |

三算法在 MPC 卡全部可执行且与 PID 卡同 seed 结果同量级（Fan/Mid 差 <2%）。证据：`runs/diag/mpc_card_acceptance/`（summary.json + 各 run UUID 目录；Mid 子目录含双卡 run）。Mid 使用 P1 工程 envelope ShipDomainProfile（诊断用途）。

### 7.7 运行方式与部署

```sh
# 重建 lane（如源变更；当前为纯冻结源码 v3 构建）
.venv/bin/python tools/original_gnc/build_native.py \
  --source ~/Code/GNC-mpc-lane \
  --dependencies ~/Code/external_sources/original_gnc_build_deps \
  --output build/original_mpc-<new> \
  --source-manifest-sha256 f7ee193e04b5165444a680b1e774e8b730639aa13dfd9f013face25ee5cc8a8d \
  --controller-package gnc/mpc_control
# 聚焦测试 / 参数诊断
.venv/bin/python -m pytest tests/test_authoritative_mpc_controller.py -q
.venv/bin/python runs/diag/mpc_heading_response_probe.py
```

卡片在 Config 步骤 04（GNC Stack）选择 "Authoritative MPC · 2026-09-21"，环境开关同 PID 卡。8010 服务加载主 checkout 代码，部署本卡需重启该服务（本任务未动生产服务）。
