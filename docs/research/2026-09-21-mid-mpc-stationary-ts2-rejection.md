# Mid-MPC Three-ship T1061.4：静止 TS2 的假船头通过拒绝

**已修复并完成原配置重放**：T1764.1 到达，硬安全 PASS、全船零碰撞/搁浅、无 fallback；实际 TS3 船尾通过。故障前 10614 帧本船状态逐值一致。

## 用户故障与根因

用户 Run `a0994641-670d-460b-9ec8-fe0199234b40`：`paper_ccta2023_multiship`、`authoritative-mpc-20260921-v1-env-on`、seed 0、dt 0.1 s、求解周期 10 s、80×5 s horizon、strict no fallback。T1061.4 s 失败：`COLREG_CROSSING_BOW`。

界面主目标虽为 TS3，失败 artifact 的 `target_key` 实际是 **TS2 / generation 1**。TS2 的职责仍为 `PAST_CLEAR / COMMITTED / GIVE_WAY`；速度为 `[-1.0165e-14, -8.5375e-15] m/s`。在绝对坐标浮点精度下，其 400 s 预测的 81 个位置完全重合。

旧 L4 判据将 `relative_at_cpa · target_displacement <= 0` 一律解释为船头通过。静止预测的位移向量为零，任何相对位置点积都是零，所以任何候选都被拒绝。这是运动方向判据缺少适用性检查，不是 IPOPT 无解，也不是新主目标 TS3 被错误分类。

## 最小修复

只改 `mid_mpc_acceptance.py::_colreg`：全部预测位置**精确相同**时，记录非强制 `COLREG_CROSSING_STATIONARY_TARGET / NOT_EVALUATED`，说明没有运动方向可定义该船尾判据。继续执行其他职责、动作期限以及全部同步 swept-hull 安全检查。

- 不设新的低速阈值，不修改距离/CPA/速度/数值容差。
- 不按场景、时间、船 ID 特判；不改生命周期、MPC 求解器、GNC 控制器或 fallback。
- 移动目标的原船头拒绝保持；只有起终点重合、途中仍在移动的预测不会被当作静止。
- 这是“该运动型几何检查不适用”，不是认证静止目标的船尾通过，更不是通用法律合规声明。

## 秒级回归

捕获用户真实 TS2 与候选，裁剪为单目标 fixture：`tests/fixtures/original_gnc/mid-mpc-stationary-ts2.json`。

- 修复前：4 failed / 5 passed，完整复现零速/浮点残余速度在 ACTIVE 与 PAST_CLEAR 下的假拒绝。
- 修复后最终 11/11：包含移动目标船头/船尾对照、静止目标碰撞仍拒绝、零首尾位移但途中运动仍拒绝、动作期限仍强制。
- 核心/装配/集成/验收聚焦：218 passed。

```sh
.venv/bin/python -m pytest tests/test_mid_mpc_stationary_crossing.py -q
.venv/bin/python -m pytest tests/test_mid_mpc_problem_assembler.py tests/test_mid_mpc_ipopt_core.py \
  tests/test_mid_mpc_ipopt_integration.py tests/test_mid_mpc_plan_acceptance.py \
  tests/test_mid_mpc_stationary_crossing.py -q
```

## 验证口径

原配置重放仅更改产物目录。原 run 与重放的 `simulation_config_hash`、`scenario_hash`、`episode_hash` 全部一致。重放直接执行真实 CasADi/IPOPT 与原 MPC native lane。

首轮诊断保存全帧，在结果汇总反序列化/GC 阶段开销过大；已停止该诊断进程，原产物保留。最终重放仅保存 evaluator 所需物理字段及单独物理轨迹，不改变推进、控制或约束。该记录策略的原故障前轨迹逐值对照另存 `prefix-parity.json`。

扩展默认船型回归与本次用户 MPC 卡分开报告。未修改 HEAD `_colreg` 在独立测试进程中执行的基线对照，不覆盖生产文件；其余生产代码无改动。不可将该对照称为另建的干净 worktree。

## 静态检查

Ruff check 通过；新增测试全文件格式检查通过，生产改动行范围格式检查通过，git diff --check 通过。生产文件其余旧格式差异在 HEAD 原文件中同样存在，未为本任务改动无关行。

## 原配置完整闭环结果

最终重放 Run：`547ec52b-8814-4e6c-8937-6fb6fb14c83c`。

| 指标 | 实测 |
|---|---|
| 终态 / 到达时刻 | FINISHED / T1764.1 s，goal_reached=true |
| 原故障前轨迹一致性 | 0–1061.3 s，10614 帧，最大本船状态差 0 |
| 本船硬安全门 | PASS |
| 本船 / 全船碰撞 | 0 / 0 |
| 本船 / 全船搁浅 | 0 / 0 |
| 本船最小中心距 / 船体净距 | 244.170 m / 215.436 m |
| 求解证据 | 191 次真实 SOLVE，全部 solver_executed=true、backend=ipopt |
| fallback | false |
| TS1 超越侧 | T344.929，右舷侧横向距离 +267.596 m |
| TS3 穿越几何 | T1609.682，目标前向投影 −1227.306 m，船尾侧 |

TS3 几何取同步真实位置与目标真实朝向，对相邻帧过线时刻插值；不是用“无碰撞”替代船尾通过。全船评价分数不能替代这条目标专属几何证据。

## 扩展回归的独立基线问题

本次聚焦 218 项通过，但不能声称旧的完整 P1 套件全绿。以下 6 项失败在修复后的测试与进程隔离的未修改 HEAD `_colreg` 对照中均复现，保留原门槛，没有为此次修复改这些测试或算法：

| 旧套件 | 两侧一致的失败 |
|---|---|
| 默认多船 | T443.1，QUALITY_CPA_RELEASE |
| 对遇 | accepted_candidate_source 为 PRIMAL_SEED，断言要求 IPOPT_BEST_FEASIBLE_ITERATE |
| 追越 | 同一候选来源断言 |
| 交叉让路 | 末端速度恢复断言：约 0.442867 m/s，而断言参照 7 m/s |
| 交叉直航 | 末端航向差约 2.368541 rad，断言上限 5° |
| 被追越 | 末端航向差约 1.168743 rad，断言上限 5° |

这些是独立的现有验收差异，不能计为本次修复通过的测试，也没有据此修改 solver、arrival 或质量门。

## 交付与限制

- 只修改一个生产判据并新增真实回放 fixture/回归；先前 GNC 响应资格问题不在此次修复范围，diagnostic-only 保留。
- 8010 服务进程启动于修复源码保存之后，已恢复监听；无需替换用户前端运行中的配置。
- 完整原配置产物：`tmp/mid_mpc_t1061_20260921/runs-thin/547ec52b-8814-4e6c-8937-6fb6fb14c83c/`。
- 持久证据：[evidence/mid-mpc-stationary-ts2-20260921](evidence/mid-mpc-stationary-ts2-20260921/)，含原拒绝 artifact、两侧配置哈希、完整物理轨迹、评估、真实求解计数、红/绿与基线日志、SHA256。
- 预防：运动型几何谓词应显式处理零运动的定义域，并用“静止且安全”“静止但碰撞”“运动且船头通过”三类反例共同约束；不需要为了本次修复重构职责模型。
