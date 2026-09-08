# Mid-MPC 威胁连续性与求解延迟修复

2026-09-08。基线 `fd4c9ca6`；复现配置取自 8010 的不可变 Run Specification：三船产品场景、Mid-MPC、God tracker、FCB45 plant / pass-through guidance / FCB45 PID、ideal / calm、seed 0、80×5s horizon、10s solve period、CPA safe/hard 200/180m。

## 根因与修复

1. **候选会遇被本船转向清空。** 基线 T=560s 的 TS2/TS3 都从 CANDIDATE 退回 CLEAR；TS3 后续在 T=1020s 被重新识别为 HEAD_ON。未锁定候选每次重新按瞬时 COG/CPA 分类，本船的返航/避让转向因此删除了仍未通过的未来会遇及动作时间。
   - 多目标提前规划现在保留候选建立时的相对运动依据。目标运动未发生显著变化、按原本船运动依据仍在接近时，保留会遇类型、候选身份与已有动作时间。
   - 当前 DCPA/TCPA 仍由当前物理状态计算，未伪造卡片数值；目标改变运动或原接近过程结束后重新评估。回归同时验证本船转向不误清空、目标真正转离仍可清空。
2. **到期动作使用上一周期航向。** 候选保留后暴露：返航转向期间，旧航向被用作新避让起点，可能使第一个 5s 控制区间无法同时满足转速和方向约束。现在在动作到期时冻结当前航向，避免把先前返航动作记成新避让动作。
3. **逐目标约束与全局恢复时间混用。** L4 曾把 TS2 的方向锁延长至整条预测的最终恢复段，错误覆盖 TS3 的后续动作。现在按已经由求解器消费的逐目标 action window 截止方向锁；无逐目标证据时仍使用原全局恢复边界。物理安全、船尾通过行、数值可行性及动作时限检查保留。
4. **已可行种子被 barrier 策略扰动。** T≈100s 的冻结问题种子已满足原始约束，adaptive barrier 仍需 39 次迭代才能获得合格改进。仅对带 ENC 约束的多目标图使用小初始值的 monotone barrier；单目标策略保留。仍执行真实 IPOPT、仍要求原数值可行性和目标改进，没有执行未经求解验收的种子。
5. **WebSocket 在事件循环等待线程锁。** 仿真在 worker 中求解，但 WebSocket 在 asyncio 线程同步等待同一把锁，放大为整个服务事件循环停顿。等待现移至 worker；串行仿真与一致快照的锁保持不变。

未改航线、场景、目标编号对应策略、horizon、求解周期、安全距离、slack、fallback 或到达阈值。

## 复现与验证

调试输入与日志位于 `tmp/debug_mid_risk_latency/`。`baseline_*` 为原提交闭环捕获，`risk_v3_*` 为修复后闭环捕获，`metrics.json` 汇总数值。提交用冻结数值夹具为 `tests/fixtures/mid_mpc_ipopt/chart_feasible_seed.json.gz`，包含原 T=100s 问题及 ENC 距离场。

- 候选连续性最小回归：修复前 `CLEAR`，修复后 `CANDIDATE/CROSSING`；当前 DCPA 仍大于 500m。
- 冻结慢问题：原图 **39 次迭代、约 898ms**；修复后 **1 次迭代、约 34ms**。原提交 `_build_graph` 在新增 `<10 iterations` 回归中失败，修复后通过。
- WebSocket 阻塞回归：原实现无法在慢锁等待期间调度其他 asyncio 工作；修复后通过。
- 正式三船测试 `tests/test_mid_mpc_anticipatory_runtime.py`：**1 passed，144.44s**。每帧检查实际 ENC 净距、每次求解检查预测 ENC 净距、全部三个目标距离、TS2/TS3 会遇连续性和船尾航迹穿越，确认到达目标且无 fallback。

| 三船闭环证据 | 结果 |
| --- | ---: |
| 到达目标时间（调试闭环） | 约 1212.5s |
| TS1/TS2/TS3 最小中心距（正式回归） | 367.05 / 333.76 / 257.50m |
| 最小预测 ENC 船体净距下界 | 48.30m |
| 最小实际 ENC 船体净距下界 | 40.04m |
| TS2 开始持续监控 / ACTIVE | 390s / 470s |
| TS3 开始持续监控 / ACTIVE | 440s / 810s |
| TS2/TS3 会遇类型 | 均持续 CROSSING 至释放 |
| TS3 首次穿越目标航迹 | 约 1085s，目标后方约 503m |
| 原 / 新运行期最大求解耗时（排除首次建图） | 846.84 / 502.08ms |
| 新求解耗时中位数 / P95 | 36.52 / 211.28ms |
| 候选质量验收 | 122 次均通过，无候选拒绝 |

**首次建图仍有一次性开销。** 正式回归在并行测试负载下首帧完整规划为约 1.42s，其中建图约 873ms、IPOPT 约 61ms。上述 34ms 是冻结问题的求解测量，不是全链路实时保证。

本轮修复随后与连续播放及 OT/HO 岸外航点调整一起提交；最新运行说明见 `mid-mpc-buffered-playback.md`。

8010 已重启并实测页面：T≈850s 显示 TS3 `CROSSING / AVOIDING`，TS1/TS2 已释放。实时监测样本包含并行测试负载；HTTP P95 约 203ms、最大 1.73s，不能据此声称所有交互延迟均消失。后续 T≈851–1150s 的 440 个请求样本，HTTP 中位数 / P95 / 最大值为约 8 / 27 / 72ms；遥测间隔最大约 659ms。已复现的 asyncio 锁阻塞由独立回归锁定。

## 验收边界

- 核心、assembler、integration、static 与提前规划检查：139 项通过（随后新增的到期基准检查另在生命周期批次中通过）。
- 生命周期、L4、性能夹具、预测证据、威胁权威、WebSocket/transport 与 playback 批次：105 项通过，2 项旧前端字符串断言失败。未修改对应 `app.js` / `situation-display.js`；用 HEAD 测试重跑仍失败，见 `baseline_playback.log`。
- 最终核心、静态、integration 与性能复核：**102 passed**；冻结 parity fixtures：**14 passed**。
- 单船扩展回归初次出现 HO / CS 末态恢复失败后中断，其余 3 项未完成。已将单目标 barrier 参数保留为原值；用 HEAD 的 `_build_graph` 单独核对 HO，硬安全门槛通过，但末速约 3.95m/s，未恢复至初始 7m/s，仍触发原末速断言（`baseline_single.log`：1 failed，4 deselected）。这不是完整单船套件通过证明，也未将该历史末态恢复问题混入本轮三船修复。
- `ruff check` 与 `git diff --check` 通过。`encounter_lifecycle.py` / `gui_server/main.py` 的原有整文件格式差异在 HEAD 上已存在，保留无关格式。

此结果针对指定仿真配置与本船对三个目标的检查，不代表任意多船布局、全海图覆盖或 MASS-L3 系统验收。
