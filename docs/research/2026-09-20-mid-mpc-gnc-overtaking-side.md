# Mid-MPC：Full Stack 与 Original GNC 的超越侧差异

## 结论与复现边界

同配置、同种子下稳定复现，未发现随机选边证据。修复前两次独立 Full Stack 运行均在 T100 锁定 PORT，前 120 秒的 121 个采样状态逐项相同；此前 8010 重启复现也与用户截图 Run 的采样位置完全一致。这不是对所有种子、所有工况的概率结论。

根因是 Mid-MPC 的地面运动预测输入，在不同 GNC 后端之间存在不一致：Original GNC 已把船体状态转为 COG/SOG，Full Stack 则直接把 heading/surge/sway 送入以 course/speed 为状态的点质量预测器。存在横荡时，heading 并不等于 COG，surge 也不等于 SOG。

正确转换为：

```text
COG = heading + atan2(sway, surge)
SOG = hypot(surge, sway)
predictor sway = 0
```

转换使用副本，保持世界坐标速度完全不变；真实船体状态、物理 GNC 与环境模型不变。严格首状态校验也比较同一表示，没有放宽容差。

初始时横荡为零，第一次规划差异还包含已声明的 GNC 响应模型与执行航线契约差异：Full Stack 的工程 course 时间常数为 9.09 s，Original GNC 的辨识值为 87.03 s。两者环境配置也不同。因此不能要求两条轨迹逐点重合；需要保证同一算法收到语义一致的状态，并正确处理其实际执行能力。

## 为什么会变成相反超越侧

原侧选择按实时地面运动评估左右候选 CPA。修复前，预测/执行偏差改变闭环运动，进而改变后续侧选择：

| 时刻 | PORT 候选 CPA | STARBOARD 候选 CPA | 结果 |
|---|---:|---:|---|
| T0 | 341.73 m | 380.46 m | 右侧 |
| T50 | 417.67 m | 326.76 m | 左侧 |

Full Stack 在待执行阶段 T50 转左、T60 回右、T90 再转左，T100 才锁定左侧；Original GNC 在 T10 就锁定右侧。重放同一批观测，只替换 course 响应时间常数，也能复现“晚锁定/左侧”与“早锁定/右侧”的差异。

关键消融：只修正地面状态输入、保留原选择策略，Full Stack 就恢复右侧超越，T265.3 驶至 TS1 并列后超前，侧向距离 354.18 m。生产补丁保留原始左右选择规则，未增加强制右侧或场景特判。

## 最终修改

1. `custom_mpc_adapter.py`：按预测器状态契约转换 COG/SOG，覆盖 Full Stack；保持原有 native route 转换行为。
2. `mid_mpc_ipopt.py`：直接调用 Mid-MPC façade 时也使用相同转换，避免入口不一致；转换幂等。
3. `mid_mpc_assembler.py`：已有响应补偿计算覆盖非 native GNC，并让已激活目标的未来计划实际消费补偿航向；最小转向量、绝对截止时间不变。过期但未完成的机动从第一可执行步满足原要求，不在重规划时重新给予 ALTER 准备步。证据中的状态表示标签与实际数据一致。
4. `mid_mpc_ipopt.py`：求解器恢复质量筛选使用与独立 L4 相同的已激活机动目标集合；未激活或已释放目标不能推迟当前机动的恢复检查。所有目标仍参与原有碰撞安全约束。

后两项由延长闭环暴露：仅输入修复在 T540 触发恢复筛选/验收对象不一致；进一步运行在 T600 暴露绝对期限与每轮重新编排的首步不一致。均通过让规划满足原验收标准解决，独立验收器未修改。

未修改 EncounterLifecycle、GNC 控制器、船舶动力学、环境、场景、随机种子、安全距离或验收阈值。原始 GNC 在 TS1 超越后受领先限制、回归 WP2→WP3 较慢的问题，仍作为独立已知问题保留。

## 验证

- **315 个针对性测试通过**：状态转换与首状态拒绝、绝对期限左右镜像、真实失败候选恢复筛选、原始数值 parity、原始/模块化 GNC 航线桥接、规划/验收/船舶会遇等。
- 修复前新增状态转换断言失败；修复后通过。恢复候选与期限用例同样有红/绿记录。
- Original GNC 独立对照运行至 300.1 s，无运行失败，保持 STARBOARD。
- 最终 Full Stack Run：`242fbcae-91cb-4537-9614-d5863bd157f6`，运行至 **1800.1 s / FINISHED**，18,001 帧，封存回放 READY、未截断。
- TS1：T100 ACTIVE，T264.9 实际从右侧驶至并列并超前，横向间距 **367.93 m**；T290 PAST_CLEAR，T300 RELEASED。
- TS2：T880 RELEASED；TS3：T1260 RELEASED。
- 独立评估：**COMPLETE / hard gate PASS**；本船最小船体间距 **270.42 m**，门槛仍为 50 m；全船碰撞 0、搁浅 0，无 fallback。
- 此次完成是 1800 s 时限完成，**不是到达终点**。COLREG 质量分数与物理安全分开报告；例如 S15=0.5、P_ahead15=1.0，不作完整 COLREG 行为验收声明。
- 广泛单会遇旧测试未全绿：主仓库早期修复版本的 HO/CS 三项失败；独立干净 `00c8f441` 基线三项也失败，失败细节不完全一致。未声称消除这些既有问题，也未将本次针对性结果冒充全库回归通过。
- `git diff --check` 通过。逐文件 Ruff 对比无新增诊断；部分既有文件存在 lint/format 失败，未顺手重排或修复无关代码。具体基线/当前结果见 `lint-delta.json`。

## 可复查证据

项目内目录：`tmp/mid_ot_side_20260920/`。

- `baseline-results.json`、`baseline-*-states.npy`：两次确定性复现。
- `diagnosis.json`：同输入、响应常数单变量对照。
- `ground-only-summary.json`：仅状态转换的消融结果。
- `ground-deadline-summary.json`、`ground-deadline-evaluation.json`、`ground-deadline-phases.json`：最终完整运行与独立评估。
- `final-regression.log`：315 passed。
- `live-verify.log`、`live-*-created.json`、`live-*-paused.json`、`live-*.jsonl.gz`：重启后的 8010 生产服务验证。
- `ot-before-after.png`：修复前、Original GNC 参考、修复后的真实地面轨迹对照。

可运行回归：

```bash
.venv/bin/pytest -q tests/test_mid_mpc_retained_route.py \
  tests/test_mid_mpc_problem_assembler.py \
  tests/test_mid_mpc_ipopt_integration.py
```

完整验证脚本使用原用户 RunSpec，文件 `full_run.py`；生产服务验证脚本为 `live_verify.py`。本报告记录提交前完成的验证；提交身份以 Git 历史为准。

## 8010 部署结果

重启后监听 PID 25056，主仓库进程。Original GNC Run `71c724aa-0fae-4182-88e8-f185319db8bb` 跑至 302.0 s，无失败；Full Stack Run `5e23d57a-4f8f-4ce6-bb01-dbb3cece0b79` 跑至 600.6 s，无失败，现为 PAUSED，保留供检查。

Full Stack 506 个实时遥测采样与最终离线闭环对齐：最大本船位置差 6.55e-11 m，TS1 已激活阶段均为 STARBOARD，执行算法均为 mid_mpc_ipopt。见 `deployment-verification.json`。临时基线 checkout 已清理，原始消融证据保留在 `tmp/mid_ot_side_20260920/ablation-ground-only/`。
