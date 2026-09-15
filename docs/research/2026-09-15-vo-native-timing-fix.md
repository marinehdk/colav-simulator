# 三船WPT3转向失效：VO与原生时钟修复

工作树：`gnc-avoidance-contract`。本轮仅修改VO求解节拍和scalar adapter的指令截止时间；GNC仍为`b3b7b2b`，不改1.2°/s参考变化率、0.25m/s²横向加速度或超时停车保护。此前VO回航修复保留。

## 根因与改动

原Run `46c3b125-95fb-468a-a464-5ba860dc6461` 在0.1s步长下，浮点累加使应到1s的间隔略小于1，VO跳过一次应有的求解，造成265次1.1s间隔。有效期仍为1s；在1111.5s前累计出现53次原生EXPIRED发布、265帧持有EXPIRED状态。GNC按保护停车，新意图重入又把转向参考重置到当前艏向，形成图中的锯齿，而不是持续向121°转向。

修复：

- VO按原生时钟纳秒精度比较“已过时间”和规划周期，消除小数步长的表示误差，不把真正迟到的求解当作准时。
- adapter以真实新求解时刻的`stack.time_ns`加原有周期生成截止时间，停止从累计浮点场景时间换算绝对原生时间。
- held tick不更新发令时刻、不续期；真正到期仍拒绝。原生零速/超时/显式返回生命周期测试保留并通过。

不是把有效期从1s加长到1.1s，不是关闭超时保护，也不是增加ROT能力。Fan共用的scalar截止时间采用同一原生时钟，Mid航线入口未改；本轮完整场景验证针对VO，未借此声明Fan/Mid全部验收。

## 原配置完整三船结果

新Run：`e007916b-0561-46e7-be1d-88c9b89947e7`。使用用户原RunSpec，VO/Truth/三船/环境OFF、seed0、默认0.1s步长，原始场景期限与安全距离不变。

| 指标 | 结果 |
|---|---:|
| 原生EXPIRED发布 | 0 |
| 最大求解间隔 | 1s，浮点记录残差约2.3e-13s |
| 目标到达事件 | 1416.7s |
| 本船对TS1最小船体净距 | 244.89m |
| 本船对TS2最小船体净距 | 209.16m |
| 本船对TS3最小船体净距 | 182.93m |
| 运行时碰撞/搁浅事件 | 0/0 |
| 独立评价全船碰撞/搁浅/未评价搁浅计数 | 0/0/0 |

约1111.4s，VO要求61.9°、GNC艏向设定64.8°、实际航迹向59.2°。旧Run相邻时刻分别约120.9°、3.7°、1.6°。修复后控制参考连续，后续规划决策也随新的实际运动改变；不把两组当作固定同指令的对照。

**TS3裕度有限：182.93m仅比原VO硬门182m多0.93m，低于190m偏好距离。** 本轮没有改变这些阈值。可以确认时序故障修复、完整轨迹通过现有硬门和默认到达；不能声称充裕鲁棒性。TS3在该实际轨迹的独立遭遇分类为CLEAR，VO记录无TS3活动规则，因此不能把结果称为“已正式验收Rule15行为”。它证明实际绕行/通过安全，不替代规则行为评价。

默认到达仍使用既有目标半径，不代表精确终点停车。原暂停Run保留，未因本轮测试重启8020；8010和main未改。

## 自动回归与继续测试

- 138项相关pytest通过：0/1024s起始的0.1s累计步长、原生截止时间、held不续期、真实超时拒绝、原生GNC生命周期、VO回航、VO既有行为、产品转发与路线接纳。
- 四个独立单船闭环（无环境超越/对遇/交叉、有环境超越）均本船硬门PASS、运行时危险事件为空、默认目标到达。
- 额外0.2s步长三船也通过：0次EXPIRED，1416.8s到达目标，无运行时危险事件；TS3最小净距182.93172m，与0.1s结果差约0.0001m。仅改变外层dt，检查时钟一致性，不更改场景几何/阈值。两种步长加四个单船场景，共6个完整闭环通过。
- 保留最终执行文件哈希和各Run原始提交/dirty身份。GNC源树无改动。修改bridge/test Ruff通过；VO原有复杂度告警不以本次修复为由重构。未跑全仓pytest/远端CI。

## 可复核产物

- [转向跟踪前后图](evidence/vo-timing-fix-20260915/turn-tracking.png)
- [三船执行与净距](evidence/vo-timing-fix-20260915/three-ship-summary.json)
- [0.2s步长三船结果](evidence/vo-timing-fix-20260915/three-ship-dt02-summary.json)
- [单船回归矩阵](evidence/vo-timing-fix-20260915/single-encounter-regression.json)
- [138项测试输出](evidence/vo-timing-fix-20260915/focused-tests.txt)
- 本机完整Run：`tmp/gnc_execution/three-ship-timing-fixed/runs/e007916b-0561-46e7-be1d-88c9b89947e7`。
- 复现：本工作树中，`PYTHONPATH=. /Users/marine/Code/Colav-Simulator/.venv/bin/python -m pytest tests/test_vo_native_timing.py tests/test_gnc_velocity_intent.py -q`。
- 完整运行脚本：`tmp/gnc_execution/three_ship_timing.py`、`three_ship_timing_dt02.py`、`vo_timing_regression_matrix.py`；生成证据：`summarize_timing_fix.py`。共享ENC资产按既有锁串行准备，不能并发覆盖。
