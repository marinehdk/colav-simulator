# TS3 Crossing：船头通过诊断与未验收修复

**Full Stack 完整闭环修复尚未验收；未提交、未重启部署。**

## 不是 OT 误分类

用户 Run `f286e6c4-90ca-4814-b486-4f0cbbf09cf7` 在 T1050–1230 的保存输入中，TS3 始终为 `CROSSING / GIVE_WAY / ACTIVE`，要求方向为 STARBOARD。T1200 截图与底层事实一致，并未被改判为 OVERTAKING。

同一配置的完整基线 Run `242fbcae-91cb-4537-9614-d5863bd157f6` 可确定性重放：T1168.766 s，本船穿过 TS3 航向线，沿 TS3 前向投影为 **+502.817 m**，即船头侧。该几何检查使用同时刻的真实位置和 TS3 航向，正值为船头、负值为船尾，不把安全距离 PASS 当成 COLREG PASS。

## 已确认的代码缺口

- T530：TS3 ACTIVE，`action_achieved=False`，`crossing_astern_required=True`。
- T540：转向幅度达标后，`action_achieved=True`；TS3 仍然 ACTIVE，但 `crossing_astern_required=False`。
- T1100、T1200：仍为 CROSSING/GIVE_WAY/ACTIVE，船尾约束仍关闭，候选继续被接受。

`action_achieved` 表示完成要求的航向改变，不表示已完成穿越/已驶过该目标。装配器和独立 L4 验收器却均以该字段关闭 CS 船尾通过检查。

当前保留的代码修改只有：

1. ACTIVE/PAST_CLEAR 的 CROSSING/GIVE_WAY 不再因 `action_achieved` 而撤销船尾约束。
2. 已排程 CANDIDATE 继续进入原先适用的预测期约束；明确限定 CANDIDATE，防止 RELEASED 目标因旧排程字段再次被约束。
3. RELEASED 仍按原职责释放语义处理。

未改场景、随机种子、控制增益、最小速度、CPA/船体距离门槛、有限时域 CPA 条件或 IPOPT 数值行拓扑。

## 已完成验证

- 新增 20 组职责状态/转向完成/穿越侧回归：修复前 **6 failed, 14 passed**；修复后 **20 passed**。
- Mid-MPC 规划、验收、装配、数值核心、航线接口与 parity 等聚焦测试：**272 passed**。
- 原始 GNC 对照 Run `335171ba-4828-4bfc-8cbd-f742981a8efc`：T1516.7 到达终点，独立安全硬门槛 PASS；实际在 T1390.058 从 TS3 船尾侧通过，前向投影 **−1037.379 m**。TS1 仍从右侧超越。
- 评估器将该对照 Run 的 Ship0–TS3 初始 pair 分类为 clear，其 Rule15 分数为 NOT_APPLICABLE。因此本报告以明确的实际轨迹穿越几何为 TS3 船尾证据；不将全船汇总 P_ahead15 当成本船与 TS3 的专属结果。

## Full Stack 阻塞及已撤回实验

仅保留上述 CS 逻辑修复的 Full Stack Run `bab45e4a-b056-4b62-aa5d-8a727f0efe79` 保持 TS1 右舷超越，但等待船尾通过时进入低速、倒车、转圈；T1664.5 数值失败。没有把该运行称为通过。

执行探针在 T1005.4 记录到：当前计划执行约 15 s（区间 3），几何 ILOS 投影已选择第 63 段；当前规划 course 约 0.085 rad，而 ILOS course 约 2.196 rad；surge 已转负。纵向积分项约 −67.5 kN，实际与请求载荷还存在较大差异。这是执行链症状证据，不足以单独断言控制器唯一根因。

时间轴/执行窗口改造试验未通过完整回归，有的改变 TS1 侧向，有的触发速度或机动期限拒绝。**这些生产代码改动已全部撤回**，差异仅保留在临时诊断目录中。

独立诊断也未产生可交付替代方案：

- 仅将通用 `speed_min_mps` 设为 3，并不等于声明最小舵速，因为 CPA 制动窗口会用另一能力字段覆盖该下限。
- 同时设置速度下限与 CPA 制动下限为 3 m/s 的对照，保留了 TS1 右舷超越，但 T770 仍未找到可行候选。未修改正式配置。
- 关闭纵向 achieved-load antiwindup 的诊断运行虽然完成时限并通过物理安全门槛，却改变了 TS1 超越侧，且未证明 TS3 已完成船尾通过；不作为修复。
- 对真实冻结 NLP 搜索普通/分段转向种子，尚未找到能替代相应低速等待解、同时通过全部原约束的候选。未修改生产求解器搜索策略。

后续需要明确 Full Stack 的普通航行低速能力边界，并继续验证规划能力声明与实际低速执行链的一致性。不能通过关闭船尾约束、放宽安全/速度验收或换后端后仍标称 Full Stack 来消除失败。

## 证据位置

`tmp/mid_ts3_astern_20260920/`：

- `user-session.json`、`user-ts3-classification.json`、`constraint-lifetime-evidence.json`：用户 Run 的分类与约束生存期。
- `reproduce_crossing.py`、`baseline-red.log`、`baseline-crossings.json`：真实船头穿越失败复现。
- `regression-red.log`、`regression-green.log`、`focused.log`：局部红/绿与 272 项测试结果。
- `original-check-summary.json`、`original-check-crossings.json`、`original-check-evaluation.json`：原始 GNC 完整对照。
- `astern-v1-summary.json`、`control-trace.jsonl.gz`：Full Stack 失败与执行探针。
- `unaccepted-timing-prototype.patch`：已撤回的执行时间轴试验，勿直接部署。
- `diagnostic-steerage-3-summary.json`、`diagnostic-surge-aw-off-summary.json`：明确修改了能力/控制参数的因果对照，不是原配置验收。

重放命令：

```bash
PYTHONPATH=. .venv/bin/python tmp/mid_ts3_astern_20260920/reproduce_crossing.py
.venv/bin/pytest -q tests/test_mid_mpc_plan_acceptance.py tests/test_mid_mpc_problem_assembler.py \
  -k 'passing_obligation_survives or rows_follow_encounter'
```

## 后续用户确认（2026-09-20）

用户已明确 Full Stack 对标真实 GNC 能力，不再另建零速等待目标；上文能力选择问题已解决。新增 f286e6c4 TS2 前后调查见 `2026-09-20-mid-mpc-ts2-transition-diagnosis.md`。运行 f286e6c4 的保存 spec 实际为 Full Stack，不能当作原始 GNC 对照。
