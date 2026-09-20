# Mid-MPC Full Stack：统一导航 Finish 判据

## 问题与根因

用户运行 `3d2b1b53-b1cd-4671-a26a-73d821625ea1` 已完成主要避碰，但在约 1587 s 绕终点，不能自动结束。

直接原因是适配器的完成策略不一致：

- `OriginalGncShipAdapter.goal_reached()` 返回 None，使用 Simulator 已有导航到达区判据：距离终点不超过 7 倍执行船长。
- `ModularShipAdapter` 未定义该方法，`__getattr__` 透传到 legacy Ship，再调用 Mid-MPC 的私有精确停车判据：距离 ≤5 m 且速度 ≤0.05 m/s。
- 同一导航任务在 Full Stack 被意外要求完成精确停车。308.7 m 的统一到达区内仍不结束，继续规划、跟踪并绕行。

用户轨迹第一次进入现有到达区为 T1410.9 s，距离 308.638 m，SOG 3.693 m/s；后来最小距离约 19.96 m，仍不满足私有精确停车条件。

## 修改

为 ModularShipAdapter 显式定义 `goal_reached()`，与原始 GNC 一样交由仿真器统一导航到达区决定 Finish。复用现有 7 船长判据，没有新增场景阈值，没有修改 MPC、控制器、避碰轨迹、碰撞检测或数值验收。

导航 Finish 与精确停车是不同任务；本修复不声称完成精确泊位停车。

此次提交同时收录此前已验证、尚未提交的 2 km 感知限制、CS 船尾义务、权限排序稳定性与共享 GNC 运动限制；其验证背景见 `2026-09-20-mid-mpc-two-km-fix.md`。

## 验证

- 扩展 `tests/test_original_gnc_goal_policy.py`，两栈共用同一边界测试。修复前 Full Stack 在 308.69 m、8 m/s 的到达案例失败；修复后通过。308.71 m 仍不结束，精确停车检查仍返回 False。
- 针对性套件 **304 passed / 66.84 s**。
- 完整 Three-ship / Mid-MPC / Full Stack Run：`b3d872ba-94e4-4ea9-b754-c66ec09fa3ee`。
- **T1410.9 s，FINISHED，goal_reached=true**，事件为 goal_reached，非 time_limit。
- 结束前 **14,109 帧本船状态与用户原运行逐值相同**，最大差异为 0；本轮 Finish 修复不改变已经认可的避碰轨迹。
- 独立安全硬门槛 PASS：全船碰撞/触礁均为 0，无 fallback；Ship0 最小船体净距 218.85 m。TS1 仍右舷超越，TS2/TS3 实际穿越均在船尾侧。
- Ruff 检查本轮修改文件、`git diff --check` 通过；此前 assembler 的既有 lint 问题未顺手修改。

证据位于 `tmp/mid_finish_20260920/`：`recorded-arrival.json`、`prefix-comparison.json`、`finish-v1-summary.json`、`focused.log` 及完整运行目录。

## 明确延期：指令平滑

按用户要求，本轮仅记录，不实施：

- 重新规划时，相邻已下发速度/航向指令仍可能跳变。
- 单条预测内部的 5 s 网格变化限制，不等于跨重新规划的连续性保证。
- 旧诊断涉及权限变化时连续性参考重置、冷启动/提前停止、几何 ILOS 与预测时间轴、真实执行响应等因素。保留证据，后续独立收敛，不将未通过试验混入本次 Finish 修复。

后续平滑验收应同时覆盖：跨求解指令增量、实际响应、TS1 超越侧、CS 船尾通过、安全硬门槛和真实 solver 无 fallback；不能仅用曲线观感判定通过。
