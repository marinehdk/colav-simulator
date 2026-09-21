# f286e6c4：TS2 前后航线与速度变化调查

状态：已完成历史记录核对、生产函数最小复现、冻结 NLP 对照；本轮未修改生产代码、未重启/替换用户会话。完整 Full Stack 修复仍未验收。

用户已确认：Full Stack 能力目标对标原始真实 GNC，不另设零速等待能力方案。落实时应统一能力契约，包括普通航行最小舵速、转弯/加减速、末端停车的适用阶段；不能简单把所有阶段速度下限改为 3 m/s。

## 1. 运行身份与观察校正

保存运行 `runs/f286e6c4-90ca-4814-b486-4f0cbbf09cf7/manifest.json` 的不可变 spec：

- `ownship_gnc_stack_id = fcb45_roll_4dof_plant+integral_line_of_sight+fcb45_marine_pid+analytic_environment_field+fcb45_environmental_load+data_driven_allocator[fcb45_main_rudder_bow_actuator_layout_v2]+resolved_actuator_dynamics[fcb45_main_rudder_bow_actuator_layout_v2]`。
- 实际是 Full Stack，不是 `original-gnc-20260914-v1-env-on`。episode 的 plant/controller/guidance 与此一致。
- tracker 为 God；T0 已有 TS1、TS2、TS3 的完整真值轨迹。GodTracker 不按图上雷达圈裁剪目标。
- 图上黄色圆半径为 **2000 m（1.08 NM）**，不是 2 NM；`web_gui/modules/situation-display.js:39` 固定常量。该圆是显示层，未控制 GodTracker 的可见范围。

| 时刻 | 实际 SOG kn | 应用规划速度 kn | 说明 |
|---|---:|---:|---|
| 350 | 13.69 | 13.00 | TS2 CLEAR |
| 360 | 13.24 | 10.33 | 任务参考速度换档、计划连续性重置 |
| 380 | 9.73 | 6.82 | TS2 CANDIDATE，距离 2530 m |
| 420 | 5.27 | 3.88 | 低于 4 kn 的是规划指令，并非实际 SOG |
| 840 | 5.27 | 3.85 | 仍低速 |
| 850 | 5.13 | 7.76 | 已开始加速，TS2 仍 ACTIVE |
| 870 | 7.07 | 9.00 | TS2 PAST_CLEAR |
| 880 | 8.76 | 9.00 | TS2 RELEASED；该时刻没有明显提速指令跳变 |

实际 SOG 来自保存状态的 hypot(u,v)，指令来自 selected_command；不可混用指令、实际速度和预测将来速度。

## 2. 350 → 360 s：没有升级威胁，为什么偏离？

确认没有 TS2 风险等级变更，但并非规划输入不变：

1. Mid-MPC 内部 LOS 的 `_wp_counter` 与最近任务航段投影不同步。350 s 本船已在 WP2 北侧约 616 m，最近投影已是 WP2→WP3；内部 LOS 仍在第 0 段，使用 6.68222 m/s（13 kn）。
2. 本船越过 WP2 的航段通过平面后，360 s LOS 切到第 1 段，速度参考成为 4.63 m/s（9 kn）。用真实 350/360 状态依次调用 `LOSGuidance.compute_references` 可重现段号 0→1、速度 6.68222→4.63。
3. TS1 已 RELEASED，但 recovery_guard 仍为 True；聚合超越速度下限是 `0.8 * planned_speed`，随之从 5.345776 变成 3.704 m/s。
4. 该速度下限进入 `_rolling_plan_identity` 的 authority_hash，造成 `COLREG_AUTHORITY_CHANGED`。旧轨迹虽通过安全重验，连续性参考和权重仍被清空。
5. 按新速度沿任务线初始化，未来与 TS2 的 CPA 硬约束冲突：12 个 CPA 行违规，对应第 68–79 区间、TS2。当前匀速 DCPA 为 1153 m，不能代表“回到任务线并换速以后”的未来 DCPA。
6. `_repair_infeasible_seed` 找到整段约 −5° 偏移的可行初值；IPOPT 只迭代 1 次后按当前质量停止规则退出，预测末端东向偏差 −155.9 m。因此预测偏移是实际输出，不是回放画错。

保留相同冻结参数与全部 NLP 行，允许继续求解：26 次迭代收敛，代价 36.17→19.59，末端偏差仍 −116.65 m。说明**预测冲突确有避让需求；仅延长迭代不能消除全部偏离**。任务航段/参考速度一致性与连续性重置同样需要修正。

## 3. 380 s：圈外监控与低速来源

- 距 TS2 2530.1 m = 1.366 NM，位于 2000 m 显示圈外，但 GodTracker 从 T0 就提供其轨迹。因此不是“传感器刚探测到”。
- 此时瞬时 DCPA 约 59 m、TCPA 323 s，进入 400 s 预测时域；TS2 由 CLEAR→CANDIDATE，调度 context 为 NEXT，原因 action_scheduled，计划动作时间约 538.8 s。不是已进入 ACTIVE 的紧急避让。
- TS1 recovery_guard 在此时解除，聚合速度下限变为 0；新的 CS 船尾/未来 CPA 约束进入优化。
- 未修复冷种子的任务速度 4.63 m/s 违反未来 CPA 行。种子修复按离散速度档搜索，命中 `0.25 * speed_max(8) = 2 m/s`。原始求解 4 次迭代退出，速度中位值约 2.005 m/s。
- 冻结同一个 NLP，保持所有原硬约束，仅关闭质量提前停止，46 次迭代收敛：代价 524.98→28.42；首指令 3.506→4.414 m/s；预测速度中位数 2.005→4.396 m/s。

这足以否定“必须持续降到约 4 kn 才有可行解”的解释。**可行性修复种子与很弱的提前停止规则共同强烈影响了执行行为**。对照仅证明冻结 NLP 存在更好的可行候选，未经过完整 L4/闭环验收，不能直接当成部署结果。

## 4. 850 s 加速：顺序误触发 + 指令接缝

840/850 s 按 TrackKey 对齐以后，各目标的避碰义务字段、聚合 directive 完全一致；仅目标顺序 `[2,1,3] → [2,3,1]`。

`_rolling_plan_identity` 按 snapshot.targets 原顺序序列化数组。因此排序变化改变 authority_hash，被当成避碰义务变更，清空连续性参考。生产函数最小复现：

```text
recorded authority same: False
sorted identical obligations same: True
AssertionError: Order-only target change invalidates unchanged COLREG authority
```

这是确定的身份构造缺陷，与 TS2 释放无关。

850 s 普通种子的第一速度增量超限，修复搜索返回 4 m/s 档，原求解 1 次迭代退出。对比 849.9/850.0 s：应用规划指令 **3.836→7.762 kn**，一步增加 **2.019 m/s**。实际船速随后逐步响应，880 s 指令仅 8.998→8.996 kn，并没有释放当刻突然加速。

当前速度/航向变化约束主要作用于每条新预测内部的 5 s 网格，第一 knot 相对于当前实测状态；它不等价于对“上一条已经下发的指令→这一条新指令”做连续变化约束。旧计划约束清空时，这个接缝尤其明显：360 s 指令航向一步 −12.32°，380 s 一步 +12.88°。有预测模型不等于已经实现跨重规划平滑，也不等于预测包含真实控制器全部动态。

## 5. 根因边界与后续修复条件

确定：TS3 船尾义务过早解除（上一轮）；本轮运行身份/显示范围混淆；任务参考航段不同步；目标排序误触发连续性重置；冷种子加提前停止使长期低速解过早成为执行结果；重规划接缝没有直接约束相邻已下发指令。

尚未确定：严格 CS 修复后 Full Stack 低速倒车/转圈的唯一完整根因。上一轮低速执行证据仍有效，但本轮不能把上述规划问题直接等同于控制器唯一根因。

按用户要求，先统一原始 GNC 能力契约，再修复上述确定缺陷。验收至少包括：顺序置换不改变权限身份；任务航段/速度参考一致；冻结 350/360/380/850 行为回归；TS1 保持右舷超越，TS2/TS3 完成船尾通过；记录跨求解指令增量和实际响应；严格安全门槛、真实 solver、无 fallback；两个 GNC 栈完整闭环分别验证。不能只调速度下限或取消船尾约束。

## 证据与复现

目录 `tmp/mid_ts2_transition_20260920/`：冻结工件 350/360/380/840/850 等；`snapshots.json`、`states.npy`；`frozen-results.json`；`authority-red.log`；`transitions.png`。

```bash
PYTHONPATH=. .venv/bin/python tmp/mid_ts2_transition_20260920/inspect_trace.py
PYTHONPATH=. .venv/bin/python tmp/mid_ts2_transition_20260920/reproduce_authority.py  # 预期失败，生产身份缺陷
PYTHONPATH=.:tests .venv/bin/python tmp/mid_ts2_transition_20260920/probe_frozen.py
```

冻结求解诊断中，序列化 Infinity 必须转 float 后交给 CasADi；早期诊断脚本误传字符串数组导致两次本地探针崩溃，已修正，未影响服务与生产代码。完整结果取自修正后的 frozen-results.json。
