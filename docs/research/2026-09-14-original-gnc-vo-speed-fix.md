# Original GNC / VO 超越低速诊断与接入修复

2026-09-14。结论：已修复 VO 路线更新继承旧折角、触发原版全路线极低速的问题。原 C++ 库及其限速逻辑未修改。完整 OT 功能验收仍未通过：1200s 内未完成超越，也不能据本轮称所有速度波动已解决。

## 复现与根因

故障 Run `5e27705c-5242-46e3-858e-20da82862cac` 使用已验证原版库，环境关闭，VO + Truth，seed=0，任务本船速度8m/s、目标船约5kn。T=521s实际速度约1.27kn。

用该 Run 每帧 planner 输出驱动同一原生栈与旧 adapter 独立重放，位置与原记录的最大误差为 **0m**，复现极低速。原版库 SHA256 始终为 `6e9f2728758b7934296e8da9bfee1a98905e038b29402c6e95ae780c6dc220fa`。

1. 旧 adapter 将已接纳路线前缀拷入每条新 VO 航向线，反复更新累积折线。
2. T=428s 的 `vo-held-intent-17` 在第15号内部顶点产生约39m、36m的相邻短段，转角100.7°。
3. 原版 manager 的半径公式 `min(L1,L2)/tan(angle/2)` 得到29.845m；按1.2°/s横摆角速度上限，允许速度为 `29.845 × radians(1.2) = 0.62508m/s`，即1.215kn。
4. 原版将最严格角点限速施加于整条路线。后续请求继续继承该角点，因此即使 VO 要求约15kn，GNC 仍输出约1.22kn。
5. 最后反馈常显示 `decel_distance_tight`，因为减速检查覆盖了先前弯道检查的 reason；仅看最终原因字符串会遗漏真正决定0.625m/s的角点。

仅减少直线采样点的试验仍失败。问题在旧前缀与新意图的组合，而非单纯点数。

另发现一处模式判定错误：T=25s已有动态目标的3个base-VO碰撞约束，但COLREG尚未承诺，旧adapter将其当成仅静态避障。这会错误地将后续航段标成cruise，解除避碰限速；之后又被其他门重新限速。新增回归先复现该错误，再补上动态目标与base-VO约束证据，保留避碰模式，不修改planner的COLREG角色。

## 修复范围

- VO 航向线以任务航线确定前方范围与恢复终点，不再以自己累积出来的旧避碰折线定义新意图。
- 存在动态目标且base-VO约束非空时，保留动态避碰段语义；不再只依据COLREG承诺来判断是否动态避碰。
- VO 提交前方航向线及任务航线尾段，不携带已执行的旧折线前缀。直线用端点精确表达；静态约束意图保留原有入口模式切换点。
- 保留当前已接纳路线作为首变化距离/侧偏接纳门的比较对象；首变化150m、侧偏500m、最短段、逆向段等门不放宽。无法通过时保持原有接纳/保持机制。
- planner 速度、航向直线和避碰标签不伪造；原版最终速度设定仍有权低于 planner 请求。
- 本次新几何仅用于 VO。Fan-MPC、Mid-MPC 沿用原接入路径；没有将本次结果扩大为它们的验证。
- 原 C++ 源码、参数、动态库、GNC保护和评价阈值均未改；未恢复P-C1/P-C2/P-C3候选补丁。

实现：`colav_simulator/original_gnc/plan_bridge.py`、`route_splice.py`。回归夹具来自故障 Run T=428s；测试先失败再通过，覆盖实际候选构建入口与原 manager 的半径计算。

## 验证结果

| 项目 | 结果 |
|---|---|
| GNC/adapter/路线及新增回归 | 88 passed |
| Ruff check、git diff --check | 通过 |
| 冻结库及生成源码指纹 | 与原版验证基线一致，无proposal |
| 最终真实VO闭环 | 1200s，2400帧，1200次SUCCESS求解，无fallback |
| 本船碰撞/搁浅 | 0 / 0 |
| 全船碰撞/搁浅 | 0 / 0，两船场景 |
| 最小本船—目标船体间距 | 659.67m |
| 全程最低本船航速 | 3.60kn（T=93s） |
| T=500s实际速度 | 修复前1.36kn；修复后6.58kn |
| T=521s实际速度 | 修复前1.27kn；修复后6.53kn |
| 超越完成 | 否；结束时仍落后目标约779m |

最终运行：`db5fa0e4-e5f2-4821-8fe6-9646bc57b145`。原始输出位于 `tmp/gnc_speed_fix_20260914/closed-loop-mode-final/`。本轮使用原场景1200s时限，没有延长时间或更改目标船使测试通过。

**速度改善不等于超越性能通过。** 最终版本固定旧planner指令重放至521s，通过了480–521s速度高于目标船的诊断断言；修复前相同重放断言失败。这仍不能替代重新求解的真实闭环，因为修改接入后实际位置已变化。本轮不声称消除所有低速或速度波动。

保留的约束：原版普通避碰标签也触发3.2m/s（6.22kn）速度上限；控制与路线切换仍有瞬态。原版“8m/s任务速度”不是任何避碰状态下都必须执行8m/s。若要求高速完成超越，需要另行确定原版速度策略与任务能力的匹配，不能在 adapter 内绕过限速。

Ruff format 检查另提示两个生产文件原有行折叠格式差异；未为本任务改动无关行。

## 留存证据与前端复验

- [速度对比图](evidence/original-gnc-speed-fix-20260914/speed-comparison.png)
- [修复前CSV](evidence/original-gnc-speed-fix-20260914/before.csv) / [修复后CSV](evidence/original-gnc-speed-fix-20260914/after.csv)
- [最终评价及关键指标](evidence/original-gnc-speed-fix-20260914/summary.json)
- [88项测试日志](evidence/original-gnc-speed-fix-20260914/tests.log)
- [证据哈希](evidence/original-gnc-speed-fix-20260914/manifest.json)

故障 Run 已封存1043帧可信前缀，0–521s，状态 `INCOMPLETE/SESSION_REPLACED`，保留旧 adapter 身份。它是历史故障证据，不会因部署修复而变化。8010重启后须创建新Run；Config保留 Original GNC / Environment OFF / VO / Overtaking，在T≈500–521s对比速度并继续检查整个超越过程。

最终部署已核对：新Run `795ce5d0-9c4e-4513-86b1-0dfd616738ac`，CREATED。实际原生库哈希不变；Run记录的Python源文件指纹与本次修复逐文件一致。见[部署身份](evidence/original-gnc-speed-fix-20260914/deployed.json)。代码及报告尚未提交git。
