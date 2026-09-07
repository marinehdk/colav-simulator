# Mid-MPC Tier2 三船问题诊断（待行为选择，未完成验收）

2026-09-07。基线 `9c428cdf`，用户现场 session `67699d8f-16a0-42dc-8135-ace8621b1d23`。配置：`paper_ccta2023_multiship`、`mid_mpc_ipopt`、God tracker、FCB45 plant + pass-through guidance + FCB45 PID、ideal actuation、calm water、seed 0、80×5s 预测网格、10s 决策周期、20s 总 deadline、严格无 fallback。实际预测窗口为 400s。

## 当前结论

**三船完整验收未通过。用户要求先提交当前修改并重启 8010，观察现象后再决定窗口外威胁方案。** 单船闭环与专项回归通过不能替代三船验收。

正在等待用户选择：对当前预测窗口之外的未来威胁，保持监控直到进入窗口再确认避让，还是允许提前锁定但延后动作。后者需要明确的分阶段动作调度；不能直接把所有未来接触都变成立即执行的转向义务。

## 已复现并修正的边界

1. **卡片读到冻结的已接受计划快照。** 新候选连续拒绝时，卡片停留在 T=0 的黄色状态；当前 Lifecycle 已记录 ACTIVE/action_started。Web 改为优先投影 Session coordinator 的最新权威快照，保留计划内部原审计快照。
2. **未来航段被航向上下界排除。** staged reference 已包含北向航段，整个 NLP 的航向界却仅覆盖当前航向 ±45°、当前航段和避让走廊。修正后纳入经过转速渐变的未来参考航向，仍保留逐步转速约束。
3. **返航验收只看离开的旧航段。** 西向转北向的合理恢复被 `QUALITY_RECOVERY_SUFFIX` 拒绝。L4 现在根据执行输入的真实任务折线独立计算恢复误差，审计覆盖完整 waypoint 输入。
4. **内侧拐角仍追旧航段。** 预测参考在大横向偏移时允许衔接相邻向前航段；需满足内侧几何、向前投影和转向可达条件。
5. **CS 纠偏候选被观测起点否决。** `COLREG_LOCKED_SIDE` 把起点已经存在的航向偏差当成新动作。未来控制不能恶化偏差，原绝对动作期限和转角仍受检查。
6. **拒绝后无条件继续旧计划。** 优化或 L4 拒绝后，仅当旧计划重新验证安全且 COLREG/路线/目标/能力身份仍兼容，才允许继续。新义务出现时不得静默执行旧计划。
7. **当前直航没有 CPA 时，物理安全行全部关闭。** 在 COLAV_STRICT 下，如果当前运动 CPA 不在窗口内，以可达范围恢复物理安全行的启用时间。保留正常物理 CPA 时刻和既有 stand-on 处理；MASS_PARITY 不改变。
8. **Tier2 横移速度引发假减速违规。** NLP 原始速度仅用 surge，L4 用总速度。严格模式统一初始总航速，避免 `TRACKABILITY_DECEL` 假拒绝；不增加容差。
9. **方向约束要求横向瞬移。** 位于航线左侧的本船，第一方向行是不可优化的观测位置，却要求已经在右侧。严格 staged 模式将该界相对当前偏差表达，要求向锁定侧改善；物理距离、转速、转向幅度约束保留。

## 复现与测量

调试脚本与中间产物位于 `tmp/debug_mid_multiship/`；原配置存于 `live_session.json`，原现场压缩审计已提取到 `live_artifacts.json`。

- `.venv/bin/python tmp/debug_mid_multiship/check_artifacts.py`：现场 10–250s 连续 25 次候选因恢复后缀拒绝。
- `.venv/bin/python tmp/debug_mid_multiship/replay.py 1`：原 T=10s 输入从 `QUALITY_RECOVERY_SUFFIX` 拒绝变为通过，终端航向从约 320° 变为约 362°。
- 原 T=395.1s 输入：纠偏候选通过，单次重放约 0.13s。
- `MID_REPLAY_LABEL=v3 ... replay.py 62`：T=620s 输入原有 TS3 预测 hull clearance 164.2m，低于 180m 硬界；安全行恢复启用后 L4 通过，重放约 0.09s。
- `MID_REPLAY_LABEL=v4 ... replay.py 35`：含 sway 的初始总航速 6.7044m/s，原第一步减速 1.50029m/s 越过 1.5m/s 界；统一速度后通过。
- `MID_REPLAY_LABEL=v5 ... replay.py 39`：负 XTE 导致不可行，原重放约 5.98s；修正方向参考界后通过，约 0.09s。

上述时间是单机窄输入重放，不代表完整前端 5 倍速保证。

## 尚未解决的三船问题

最新中间版本 `v6` 在 564.9s 结束，未完成任务；行为是提前叠加远期目标的转向义务后驶入陆地。该版本不能用于验收。

- T=420s，TS3 当前-motion TCPA 约 599.65s；T=430s 仍约 584.03s，超过 400s 预测窗口，但 Lifecycle 已确认 ACTIVE。
- 同时存在 TS2 的 CS 义务和 TS3 的新 CS 义务；走廊由约 19.8° 增至约 35°。
- 该中间运行仍出现不可行/超时求解：不能宣称倍速卡顿已彻底修复。
- 此次诊断未新增静态障碍规划能力，也未关闭搁浅终止或放宽安全门。

离线定位保留求解输入、结果、生命周期输入和采样船舶状态。后续调试 harness 清理已另行记录的 raw frame 历史以避免失败导出时展开数 GB 重复审计；此举不修改运行控制或生产保留策略。早期中间运行因失败导出大量历史帧而变慢，已中断并保留定位产物；不把这些时间当作 solver benchmark。

## 已完成检查

- `regression_v6.log`：214 项专项通过，覆盖 assembler、IPOPT core/集成、独立 L4、生命周期权威、预测证据、C++ parity fixtures、Web threat projection/transport、rolling plan。
- `current_focused.log`：当前相关集中复查 175 项通过。
- `single_encounters.log`：`tests/test_mid_mpc_single_encounter.py` 五项闭环通过，435.76s；涵盖 HO、CS give-way、CS stand-on、OT、overtaken。该套用既有单船 fixture，不等同于用户 Tier2 三船验收。
- Python Ruff 与 `git diff --check` 通过；新修改的算法与核心测试文件格式已检查。`gui_server/main.py` 和旧 `tests/test_web_evidence_transport.py` 在基线就不满足全文件 formatter，未顺手重排无关代码。
- 前端 249/251 通过。两项失败均是未修改的静态 cache-bust 断言仍要求旧版本标签：`config-shell-static.test.mjs`、`shell-theme.test.mjs`。当前任务没有改动浏览器资源文件或这两项测试，不能称前端全绿。

没有放宽硬安全门、强制 PASS、替换求解器或新增 fallback。完整三船验证仍待后续行为选择和修复。
