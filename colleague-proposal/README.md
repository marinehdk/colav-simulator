# Colleague Proposal Package（同事端修复参考包）

日期：2026-09-12。性质：**参考实现**——在我方vendored提取树（与快照逐哈希对应、仅机械编辑）上验证过的补丁，供同事在原ROS2仓库评审采纳。每个diff独立可读：unified diff对同事原始路径 + 每hunk注解块（`//` 行：问题/证据/更改/预期效果/验证方法；机械应用前 `grep -v '^//'` 剥离）。

## 补丁清单

| # | 文件 | 主题 | 依据 |
|---|---|---|---|
| P-C1 | `P-C1-avoidance-speed-policy.diff` | avoidance速度策略分离：emergency限速、普通avoidance巡航速跟踪 | R3/S1；p5/p6 SOG证据 |
| P-C2 | `P-C2-corner-degradation-scoping.diff`（基于P-C1树） | 角降级分段作用+通过顶点恢复+舵速floor | R13；fan-HO 0.892平台、vo-CS 0.321平压数组 |
| P-C3 | `P-C3-decel-check-awareness.diff`（基于P-C2树） | 减速检查改执行速度+剩余距离+模式floor+revision滞回 | R14；`decel_distance_tight`静止触发 |

## P-C1关键发现（协议层）

`coordinate_transform_node navigation_mode_code()` 把全部avoidance字串折叠到code 6，`ship_guidance_node navigation_mode_from_code()` 把6解码为字面`"emergency_avoidance"`（帽的门控键）——**仅改guidance无效**（已探针证实）。补丁方案：沿用贵方自己的仲裁区分（`route_arbitration_policy.hpp emergency_behavior()`），emergency族保code 6、普通avoidance走新code 10，CT的guard/FAP谓词同时接受6+10（防护语义字节级不变）。**贵方若另有消费code 6的节点，需确认对新code 10的处理**（当前快照内仅CT/guidance/manager消费）。

## P-C2/P-C3关键发现（同一缺陷两面）

`active_route_manager_node evaluate_avoidance_plan` 角点循环对全航线顶点取min得**全局**`suggested_max_speed_mps`，`apply_speed_degradation`平压整个speed数组且无恢复（每 kink r=42.6m → 0.892 m/s = r×1.2°/s；r=15.3m → 0.321 m/s 锁到终局）。`decel_distance_tight`为同一评估器的计划剖面检查：用请求速度算242m需求 vs 165m段、船静止(0.0 m/s)时也触发。补丁：分段作用（顶点邻接段）、通过顶点恢复、舵速floor 2.5、执行速度+剩余距离+模式floor（cruise≥0.2 vs berthing 0.08）+revision滞回。**调参建议**（未改默认）：`max_yaw_rate_deg_s` 1.2°/s ⇒ 7 m/s需半径334m，任何中度弯都触发降级——建议放宽或按min(请求,执行)速度计算需求半径。

## 我方验证

- 构建：`tools/original_gnc/build_native.py --proposal P-C1 [P-C2 P-C3]`；identity链（verify_build+manifest+extraction ledger含`colleague-proposal`块）全过；82单测/构建全绿（每套<12s）。
- 原生探针（等价输入对拍 baseline vs proposal）：
  - P-C1：`avoidance`/`collision_avoidance` → 7.8 m/s（解除）；`emergency_avoidance` → 3.2（保留）；`cruise`不变。
  - P-C2：kink r≈70m航线 speed数组 `[1.47×4]`→`[2.5,2.5,2.5,7.8]`（分段+floor+开放段保请求速）。
  - P-C3：静止起始 B1 `decel_distance_tight`→ACCEPTED；执行7.8时仍正确触发；同revision重发不再复标；dp_hold保持0.08参数。
- 闭环战役：p7（P-C1）与p8（P-C1+2+3）24格对比基线——见下节（待填）。

## 配套修改提示（P-C1采纳后我方将同步提交）

planner包络假设与执行策略联动：我方VO包络窗口此前按"avoidance段执行≤3.2"设定（[steerage, cap]）。P-C1后普通avoidance段不再限速，我方将把包络上限同步为巡航速（emergency语义保留3.2参考）。**p7单P-C1实测出现过1格planner INFEASIBLE回归（vo-OT-E0，非碰撞、桥诚实拒绝）**，即此联动未做时的结果——同事采纳P-C1时请预留我方PR联调窗口。

## 验证结果（闭环，24 格产品矩阵 seed 0）

| 轮 | 构建 | COMPLETED | 硬安全 | goal | 备注 |
|---|---|---|---|---|---|
| p6 基线 | 未打补丁 | 16/16 (VO/Fan) | 全 PASS | 2 | 主分支现状 |
| p7 | P-C1 | 15/16 | 全 PASS | 2 | vo-OT-E0 planner INFEASIBLE（包络-执行失配） |
| p8 | P-C1+P-C2+P-C3 | 15/16 | 全 PASS | **3** | fan-HO-E4 新达标；vo-OT-E4 INFEASIBLE（同类换格） |
| p8b | + 包络耦合（已回退） | 15/16 | PASS 但 VO-HO 净距 453→79/90 m | 0 | 耦合摊薄安全余量、无 goal 增益 → 回退，保持保守包络 |

要点：(1) P-C2/P-C3 落地后 vo-OT-E0 从 p7 回归中恢复（COMPLETED+PASS 1061 m）——manager 速度数组修复直接改善 planner 可行性；(2) 唯一开放格 vo-OT-E4 为 planner 侧包络-几何失配（诚实拒绝、无安全事件），与同事补丁解耦，我方 planner track 继续跟进；(3) goal 提升受 VO 末端与遭遇几何共同限制，增速使净距变薄——**安全余量优先于任务速度**，未采用激进包络。

## PLR/回归说明

## 给同事的实施说明

1. 三个diff按 P-C1 → P-C2 → P-C3 顺序应用（后者基于前者应用后的树）；均提供colleague原始路径头。
2. 每个diff头部注明对应我方登记册条目（R3/R13/R14）与我方证据档路径；采纳后我方将对应条目转`verified-fixed`并以贵方仓库版本重跑24格回归。
3. 需贵方答复的两项（不阻塞本包）：S3 warm-seed不变量意图（我方Mid候选接受率）；`ship_config.yaml`是否为active_route_manager_node补`minimum_steerage_speed`键（当前补丁内置安全默认2.5=guidance值）。
4. 我方对应验证环境：patch→`build_native.py --proposal ...`→24格产品矩阵（seed 0）+COLREG v2评分；工具随我方仓库交付。
