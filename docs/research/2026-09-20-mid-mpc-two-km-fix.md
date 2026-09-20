# Mid-MPC：2 km 感知边界与三船避碰修复

本文件保留 2 km 阶段的历史验证结果。后续导航 Finish 已对齐统一判据，见 [Finish 修复](2026-09-20-mid-mpc-full-stack-finish.md)；指令平滑按用户要求延期。

## 交付范围与边界

保留并验证：GodTracker 的 2000 m 感知边界、CS 船尾义务生存期、目标排序不改变权限身份、Full Stack 复用原始 GNC 的普通航行运动限制。

**不能宣称整航程已完善**：跨重规划指令完全平滑、末端停车/到站仍未验收。两栈此处均按原 1800 s 时限结束，未触发 goal_reached。未放宽安全、船尾、数值或无 fallback 门槛。

扩展的航段恢复、终点制动和预测时间轴试验没有同时满足行为要求，已撤回。当前生产源码不包含这些试验；差异留在 `tmp/mid_ts2_transition_20260920/unaccepted-expanded-recovery.patch` 供后续定位，不能直接部署。

## 确认根因与保留修改

1. GodTracker 原先直接把所有真值目标生成 TrackSnapshot，无探测距离过滤。现在在生成轨迹和测量前按本船位置计算欧氏距离，仅接收 ≤2000 m 的目标；边界包含 2000 m。离圈后不再输出该目标真值；重新入圈按已有 generation 规则重新建立轨迹。此限制作用于两种 GNC 共用的感知入口，不是仅隐藏 UI 颜色或截断威胁显示。预测仍可外推已观测目标的未来位置。
2. CROSSING/GIVE_WAY 的 action_achieved 只表示完成规定转向，不表示已完成交叉通过。ACTIVE/PAST_CLEAR 阶段继续保留船尾约束，RELEASED 不因旧 planned_action 再启用；NLP 和 L4 使用一致义务。
3. 目标距离排序变化曾改变 authority_hash，从而清空旧计划连续性。现在按 TrackKey 规范化目标和 required_targets 的顺序；真实义务变化仍会改变身份。
4. Full Stack 此前未声明普通航行最小舵速，加减速和转向边界也更宽。现在通过 OriginalGncConfig.parameters() 读取同一冻结源：最小舵速 3 m/s、速度上限 8 m/s、普通转率 1.2°/s、速度变化率 0.08 m/s²；若 Full Stack 控制器声明更小转率，则保留更严格限制。组装器不再把最小舵速和 CPA 制动下限的适用性错误地绑定到“是否有原始 GNC 路线前缀”。

运动限制共享不等于两套执行模型完全相同。Full Stack 的工程响应常数仍为航向约 9.09 s、速度 12.5 s；原始 GNC 当前路线输入的辨识值约 87.03 s、24.07 s。后续应对实际执行链做响应资格验证，不能把这些数字机械设成相同后声称动力学已一致。

## 红绿回归

- `tests/test_god_tracker_lifecycle.py`：原实现 2 failed/2 passed，2000.1 m 与 2530 m 目标错误可见；修复后和 tracker snapshot 合计 6 passed。覆盖精确边界、全局坐标、入圈、离圈、重入 generation。
- `test_rolling_authority_ignores_target_and_required_key_order`：修复前 authority_hash 不同，修复后相同。
- Full Stack adapter 运动边界：修复前 0.05 rad/s，修复后读取原始 GNC 1.2°/s、0.08 m/s²、3–8 m/s 普通航行政策。
- CS 生命周期上一轮红绿回归继续保留。
- 最终保留源码针对性套件 **299 passed / 54.76 s**，日志 `tmp/mid_ts2_transition_20260920/retained-final-focused.log`。
- 新改动 Ruff 检查通过；assembler 及其测试存在 HEAD 已有的复杂度、行长等问题，比较确认没有新增诊断。`git diff --check` 通过。没有顺手重格式化旧代码。

## 完整三船证据

| 项目 | Full Stack | 原始 GNC |
|---|---|---|
| Run | `3be597da-dfdf-462d-a826-58ceb722a0d3` | `2dcd7e34-494f-4b8b-bf12-a6b91a8948a8` |
| 状态 | FINISHED，1800.1 s 时限 | FINISHED，1800.1 s 时限 |
| 到达终点 | 否 | 否 |
| 独立安全硬门槛 | PASS | PASS |
| 全船碰撞/触礁 | 0 / 0 | 0 / 0 |
| Ship0 最小船体净距 | 218.85 m | 214.17 m |
| TS1 超越 | 271.9 s，右侧 538.91 m | 374.9 s，右侧 268.34 m |
| TS2 首次实际穿越其航向线 | 1027.03 s，船尾侧 −1621.45 m | 1218.04 s，船尾侧 −730.65 m |
| TS3 首次实际穿越其航向线 | 1294.96 s，船尾侧 −957.34 m | 1602.21 s，船尾侧 −991.62 m |

Full Stack 运行中 TS2/TS3 的 ACTIVE/PAST_CLEAR 身份均为 CROSSING/GIVE_WAY，没有用 OT 身份解释船头通过。

Full Stack 中 TS2 首次被感知约 431.2 s、TS3 约 704.5 s。冻结规划输入审计 162 条目标记录，最大距离 1999.274 m。原回放 f286e6c4 在 380 s、2530 m 的 TS2 提前升级不再发生。运行时刻和相遇时序随感知限制变化，不能机械沿用旧回放的 380/420/880 s。

几何穿越证据与汇总 Rule15 分数分开报告；全船评估还含不受控目标船对。上述 PASS 是指定安全硬门槛，不是完整 COLREG 法律合规认证或全场景验收。

保留版 Mid-MPC 集成源文件 SHA256 与 Full Stack 验证运行 manifest 的 algorithm module hash 相同。原始 GNC 的最终对照保持同样轨迹穿越结果。

## 未通过试验与后续工作

- 仅范围/排序/CS 修复：Full Stack 在 683.2 s 失败，不能交付；共享源运动限制后才完成避碰段。
- 扩展终点制动试验发生过严格 TRACKABILITY_ACCEL 拒绝；未放宽容差。
- 同时施加额外 LOS 换段到原始 GNC，会与其已有执行约束重叠并触发 COLREG_CROSSING_BOW 拒绝；撤回。
- 扩展回航/时间窗口方案改变了相遇时序，出现前方穿越、晚期绕行或低速问题；未采用。
- 保留版跨重规划最大速度指令跳变约 1.279 m/s，说明“指令完全连续”尚未解决。现有 5 s 预测网格速度变化约束不等于相邻已下发指令变化约束。

后续必须在真实执行契约上解决连续性、响应模型和末端停车；不能靠隐藏目标、强制指定场景侧向、关闭船尾约束、换后端或放宽门槛完成验收。

## 复现与证据位置

汇总：`tmp/mid_ts2_transition_20260920/retained-acceptance.json`。

完整运行：`tmp/mid_ts3_astern_20260920/runs/<Run>/`。Full Stack 对应 `range-capability-v3-*`；原始 GNC 对应 `range-response-original-*`。

```bash
.venv/bin/pytest -q tests/test_god_tracker_lifecycle.py tests/test_tracker_snapshot_contract.py
.venv/bin/pytest -q tests/test_mid_mpc_ipopt_integration.py -k rolling_authority
PYTHONPATH=. .venv/bin/python tmp/mid_ts2_transition_20260920/verify_range.py \
  tmp/mid_ts3_astern_20260920/runs/3be597da-dfdf-462d-a826-58ceb722a0d3
PYTHONPATH=. .venv/bin/python tmp/mid_ts3_astern_20260920/reproduce_crossing.py \
  tmp/mid_ts3_astern_20260920/runs/3be597da-dfdf-462d-a826-58ceb722a0d3/decision/frames.jsonl.gz retained-full
```

## 8010 生效状态

已通过原 LaunchAgent 重启；监听 PID 由 28966 变为 68993，cwd 为主工作区 `/Users/marine/Code/Colav-Simulator`。HTTP 服务已恢复。重启前会话为 CREATED/T0，没有正在运行的仿真。旧封存回放不改写；需新建运行采用新感知边界。修改尚未提交 Git。
