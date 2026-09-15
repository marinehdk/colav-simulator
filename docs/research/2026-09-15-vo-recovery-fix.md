# VO回航震荡修复

日期：2026-09-15。实施于隔离分支`codex/gnc-avoidance-contract`。本轮只改VO及其名义参考；权威GNC仍为`b3b7b2b`，艏向参考变化率1.2°/s、横向加速度0.25m/s²、所有硬碰撞距离门保持。未合并main。

## 修复内容

1. **清除目标不再冒充新危险目标。** VO曾把任意空规则目标都视为尚未分类，连已经通过、TCPA负值的船也触发右转优先，造成回航参考额外约11°右偏。现在该临时策略只覆盖满足既有危险资格且TCPA非负的未分类目标。活动让路承诺与全部硬碰撞约束仍保留。新回归从11.25°错误偏航转为通过；已有窗口外偏航回归也恢复通过。
2. **VO参考提前考虑横移。** 将当前横向误差、实测响应时间内的横移，以及按既有转向率转回平行期间的横移共同用于回航参考。参考收敛增益不超过两倍响应行程对应的增益；未把这个规划模型当作新的物理能力。
3. **终点有明确减速参考。** 最后航段按剩余沿航线距离与预测/响应时间降低期望速度，避免始终以巡航参考预测越过终点；VO仍独立选择满足硬约束的速度和方向。内部航段保持原速度计划。末段出现低速时，可在五阶段速度面板看到来自VO本身的减速请求。

GNC原生速度入口继续执行航迹向/SOG；VO此链仍使用VO侧LOS名义参考，不切换到原版GNC ILOS。GNC ILOS/ALOS航线路径入口、Fan及Mid本轮未改。

## 真实超越前后对比

原Run：`1bf72eb5-6a71-4097-acef-5f63d7e43954`。最终新Run：`108f4710-7512-4f5f-ae83-10f81505ce7f`，同一OT/VO/Truth/OFF配置与场景期限。

| 指标 | 原Run | 修复版 |
|---|---:|---:|
| 550s后的横向误差范围 | −185.76至+421.94m | +49.11至+159.57m |
| 反复越过原航线 | 有 | 该回航段无 |
| 最终记录横向误差 | 暂停798s时约300m | 107.06m |
| 本船最小船体净距 | 本轮不重评暂停前缀 | 350.33m |
| 运行时碰撞/搁浅事件 | 暂停现场 | 0/0 |
| 默认目标到达 | 暂停现场 | 777s |

**边界：未声称贴线回航、精确终点停车或实船资格。** 修复版末段仍因静态避障修正方向，图中仍能看见一次较小的偏移；最终107m偏差符合既有约309m目标半径，但不是零误差。解决的是原先大幅、反复越线且振幅增长的问题。目标附近安全约束不能为了画出直线而关闭。

最小净距高于原VO硬门182m和偏好190m；未降低标准。记录最后一帧776.5s，运行时goal_reached事件777s，不能把两者时间混用。另核对events.jsonl，避免仅靠独立评价遗漏终止帧风险。

## 验证

- 114项相关pytest通过：回航横移、终点减速/内部航段不减速、清除目标偏置、VO论文行为重建与既有回归、速度合同、原生转发和产品绑定。
- 最终版本真实VO矩阵：对遇OFF、交叉让路OFF、超越E4均本船硬门PASS、运行时危险事件为空、默认目标到达。加上上表超越OFF，共4格。
- 未跑全仓pytest/远端CI，不推导多船全矩阵或正式COLREG合规；Mid既存执行验收缺口仍未处理。
- 修改的guidance/interface/test Ruff通过。VO模块原有3项复杂度告警保持，未借本任务重构。

两个根因都需要处理：只改右转偏置的对照仍出现超过300m反向偏离；仅预判横移仍有二次摆动。扩大前视但不闭合其他问题的试验未作为交付。试验中的软TTC成本截断没有解决根因，已撤回，最终成本公式未改。

## 证据与复现

- [前后对比图](evidence/vo-recovery-fix-20260915/before-after.png)
- [超越汇总](evidence/vo-recovery-fix-20260915/overtaking-summary.json)
- [其他3格](evidence/vo-recovery-fix-20260915/matrix-summary.json)
- [测试输出](evidence/vo-recovery-fix-20260915/focused-tests.txt)
- 本机完整Run：`tmp/gnc_execution/vo-ot-damped-v7/runs/108f4710-7512-4f5f-ae83-10f81505ce7f`。
- 本机矩阵：`tmp/gnc_execution/vo-recovery-matrix-v7/`。测试工具：`tmp/gnc_execution/closed_loop.py`、`vo_recovery_matrix_v7.py`、`summarize_vo_recovery.py`。
- 本工作树运行`PYTHONPATH=. /Users/marine/Code/Colav-Simulator/.venv/bin/python -m pytest tests/test_vo_recovery_guidance.py tests/test_kuwata_vo_paper_reconstruction.py tests/test_kuwata_vo_regression.py tests/test_gnc_execution_speed_contract.py tests/test_original_gnc_held_intent_geometry.py tests/test_original_gnc_product.py -q`。

运行证据保留执行时的提交/dirty身份，没有事后改写成干净提交。最终执行源码哈希另存于证据目录。
