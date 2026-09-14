# 权威GNC修订与三算法接入报告

日期：2026-09-14。**开发实现已落地；完整避碰资格未通过；8010未切换。**

## 输入边界与唯一维护源

权威源：`/Users/marine/Code/GNC`，分支`codex/avoidance-execution-contract`，修订提交`b3b7b2b`。从冻结包导入后建立Git仓库；原包仅作历史证据。本版本已修改行为，不能称为“与未修改2026-08-24原版行为相同”。一致性比较对象是同一修订源的独立ROS C++实现。

集成：`/Users/marine/Code/.worktrees/Colav-Simulator/gnc-avoidance-contract`，分支`codex/gnc-avoidance-contract`。Colav只提取并集成源，不在生成C++中另加行为补丁。主checkout既有未提交内容、8010和8014保留。

| 算法 | 原生输出 | 接入方式 | 恢复阶段 |
|---|---|---|---|
| VO | 航迹向＋SOG | 原生VelocityIntent | 持续发送自身巡航/恢复指令 |
| Fan-MPC | 航迹向＋SOG | 同一VelocityIntent | 持续发送自身巡航/恢复指令 |
| Mid-MPC | 避碰路径＋速度计划 | RoutePlan/原航线接纳链 | 保留显式航线与返回合同 |

VO/Fan不再生成其未规划的避碰折线、回航段；约束消失也不自动切换到另一导引器。意图绑定父航线、版本、求解ID、模式和截止时间。保持旧解的tick不能续期。接纳拒绝显式失败；到期由GNC停车保持，等待新意图或显式返回。Mid的路线几何门仍保留，包括普通路线更新500m前视规则。

## 3.2m/s如何处理

原源码把普通avoidance与emergency_avoidance都编码为模式6，普通避碰因此进入紧急3.2m/s限速。修订在权威源码中把普通模式分为10，紧急仍为6；原有“任意避碰”保护同步覆盖两者。

普通/巡航当前上限8m/s；紧急仍3.2m/s。3.2是保留的历史策略参数，没有新增实船适用性证明。VO消费GNC速度合同作为硬上限；TCPA舒适门不能重新打开被执行侧禁止的速度。速度上限不是跟踪保证：航迹向转换、运动约束、控制滞后、分配降级仍可能改变执行结果。

原生输入跟踪期望航迹向和SOG，向原自动舵提供艏向与有符号船体纵向速度。加入有界、随速度调度的航迹向外环；原PID、船体方程、执行器增益保留。SOG按侧滑投影为surge；不可把SOG与surge当成同一物理量，也不可把模型当前速度再叠加一次流速。

五阶段面板：任务SOG、规划SOG、接纳值、GNC surge、实际SOG。显示模式、限速原因、来源身份、各阶段时间。修复面板读取下一积分步状态的问题：记录帧保存GNC投影，展示使用该帧；旧帧缺失证据时不借用当前状态。此项未改变物理执行。

## 可复核身份与对照

- 源清单：`bf5de3f2b5717b62bf2755aa71e261e0cc7b30c952ea89dd5e166f8aa6b16059`
- 本机库：`c5541abb4917bd94064c4b8a1944fc4c945fda16380ea43f5132cd54034388ce`
- 集成构建：`build/gnc-velocity-v5`；该工作树默认指针指向此目录。
- A4000独立参考：`/home/marine.huang/gnc-authority-vnext-pYlK2N/reference-v5`，13个ROS包构建通过。参考进程未加载本机嵌入库。
- 55秒输入序列覆盖巡航、普通、紧急、零速、超时、显式返回；E0/E4共1980模块状态样本通过。
- 完整C++发布流共36334条、824915数值字段通过原有容差；E0全零差，E4最大力差1.36e-12、力矩差8.73e-11。安装路径差异先验证源资产哈希再归一化，未放宽数值门。
- 路线和速度输入分别重测响应；velocity航迹向时间常数39.43s、R²0.974；速度12.51s、R²0.941。它们是有限激励范围拟合，不是全状态可达性证明。

此对照使用受控同输入/时钟参考，不等于ROS异步部署验证，也未重跑旧28组完整保真矩阵。

## 完整运行链结果

使用真实RunSpec→真实规划器→adapter→新GNC→轨迹与独立评价。未更改场景时长、安全阈值或启用fallback。表中净距为本船对目标的船体最小净距；PASS只是独立安全硬门，不是完整COLREG与任务验收。

| 算法/场景 | 环境 | 最小净距m | 本船硬门 | 默认目标到达 |
|---|---|---:|---|---|
| VO超越 | OFF | 350.33 | PASS | 是，804s |
| Fan超越 | OFF | 261.96 | PASS | 是，721s |
| VO对遇 | OFF | 217.07 | PASS | 否 |
| Fan对遇 | OFF | 259.76 | PASS | 是 |
| VO交叉让路 | OFF | 223.16 | PASS | 是 |
| Fan交叉让路 | OFF | 288.02 | PASS | 是 |
| VO超越 | E4 | 327.88 | PASS | 是 |
| Fan超越 | E4 | 259.25 | PASS | 是 |
| Mid交叉让路 | OFF | 785.33 | PASS | 否 |
| Mid超越 | OFF | 未完成 | L4 QUALITY_CPA_RELEASE拒绝 | 否 |

7格矩阵的运行时碰撞/搁浅事件均为空；不能由本船PASS推导所有目标船安全或正式COLREG合规。Mid交叉仅移动约62m仍可得到安全PASS，更说明安全与任务完成必须分开。Mid使用已有P1测试域配置，不是船型资格认证。

无环境超越速度抽样（m/s）：

| 算法/时刻 | 规划SOG | GNC surge | 实际SOG |
|---|---:|---:|---:|
| VO 180s | 7.742 | 7.742 | 7.542 |
| VO 360s | 8.000 | 8.000 | 7.635 |
| VO 521s | 7.742 | 7.958 | 7.523 |
| Fan 180s | 8.000 | 7.999 | 7.799 |
| Fan 521s | 8.000 | 8.000 | 7.800 |

521s的VO新请求与上一控制采样可能不同，不把两个阶段当成即时相等。修订后已无普通模式固定3.2限速；实际航速约低0.2m/s属于当前跟踪结果，不能包装成“严格8m/s”。末段减速可能来自规划器自身：VO最终请求约0.323m/s，Fan约2.725m/s。

VO/Fan超越的沿原航线相对目标领先约1902/1938m。终点横向偏差约280/18.5m。当前仿真到达门为7倍船长≈308.7m，故“到达”不是精确回航或终端停车。严格恢复保持尚未充分证明，不以运行结束替代。

## 保留的失败与验收缺口

1. Mid超越最终触发L4 QUALITY_CPA_RELEASE。此前54.5s已出现GNC几何降速：可用转弯半径33.51m，要求381.97m，航线速度被降至0.702m/s，实际1.886m/s。这里不是3.2m/s紧急策略；不能把最终L4拒绝直接归因为规划器单独故障。仍需定位Mid路径、adapter前缀拼接和GNC动态接纳之间的不匹配，没有降门、改成VO或绕过路线校验。
2. VO对遇、Mid交叉未到达目标；完整恢复、停止与多船矩阵仍需继续验收。
3. 拒绝的VO参考前视试验在1023s发生运行时搁浅；独立评价却因缺少终止后最后一帧给出PASS。该试验已撤回。保存失败证据，不计入上表；终止帧录制缺口仍存在，当前结论同时核对运行时事件。
4. 未声明完整正式COLREG合规、全船安全或实船部署资格。当前源状态保持IN_DEVELOPMENT_NOT_ACCEPTED。

## 自动验证与复现

最终focused：109 passed；前端速度面板：6 passed。未跑全仓pytest/远端CI。修改文件Ruff除VO原有3项复杂度告警外通过；旧HEAD同样触发这3项，未借任务改写该算法。

本机执行：在本工作树设置PYTHONPATH=.，使用主checkout的.venv/bin/python。

- 原生输入与生命周期：`pytest tests/test_gnc_velocity_intent.py tests/test_gnc_execution_speed_contract.py`
- 转发与产品帧：`pytest tests/test_original_gnc_held_intent_geometry.py tests/test_original_gnc_product.py`
- 独立源输入序列：`tools/original_gnc/check_velocity_input_reference.py --source /Users/marine/Code/GNC --build build/gnc-velocity-v5 --output <新目录>`；独立ROS侧增加`--reference-drivers`，并保留ROS Python环境。
- 真实闭环入口：`tmp/gnc_execution/closed_loop.py`、`closed_loop_fan.py`、`closed_loop_mid.py`、`matrix.py`。运行使用共享ENC资产锁，不能并行覆盖同一海图缓存。
- 全量Run与轨迹：`tmp/gnc_execution/`；原生/源发布流和响应测量：`build/input-*-v5*`、`build/response-measurement-v5`。
- 持久精简证据：[evidence目录](evidence/gnc-authority-20260914/)。其中matrix-summary保留各Run绝对路径；未把build目录当作可移植发行物。

隔离预览：<http://127.0.0.1:8020/>。用于输入链和速度解释验收，尚未替换8010当前基线。
