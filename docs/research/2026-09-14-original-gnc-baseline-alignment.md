# Original GNC 原版对齐报告

2026-09-14。范围：恢复已验证的原 C++ 业务行为，暂停航速优化；不修改原方程、控制增益、保护或安全门。

**交付结论：当前 Original GNC 卡片绑定已验证的冻结原版 C++ 基线；在已测同输入、时钟和回调顺序下满足原版移植保真标准。允许进入前端避碰功能验收，尚未通过场景性能或系统安全验收。**

本次基于本地 main `bb6e36aa`，仅调整部署指针及报告；未新增 GNC 行为实现。报告交付时重新读取 8010 API，确认原版基线仍在用。

## 评价标准与覆盖范围

依据此前 [嵌入保真评估](2026-09-10-original-gnc-fidelity-report.md) 和 [测试集成方案](2026-09-10-original-gnc-test-integration-plan.md)。

| 评价项 | 结论 | 证据范围 |
|---|---|---|
| 冻结来源与构建身份 | 通过 | 源清单、生成文件及实际动态库哈希；无候选补丁 |
| 原 C++ 业务保真 | 已测范围通过 | 方程、控制参数、保护及降级保留；独立原端参考逐回调比较 |
| 本地 adapter 接线 | 聚焦回归通过 | 原生实例隔离、状态/参考映射、内部周期、路线合同、禁止旧控制链接管 |
| 历史同输入长回放 | 历史通过，完整性本次复核 | 28组、224次模块回放；本次未重跑全部长回放 |
| 原生 ROS 异步整体轨迹等价 | 未证明 | 原评估存在显著差异；共同调度通过不能覆盖自由异步执行 |
| VO/Fan/Mid 避碰及 OT 航速表现 | 待用户验收和后续诊断 | 不能沿用 proposal-full 的场景成绩 |
| 全船安全、COLREG、目标到达、D3 | 不作通过结论 | 必须按新原版 Run 独立评价 |

原 C++ 核心覆盖坐标转换、路线管理、导引、控制、推力分配、船舶动力学；环境覆盖风、流、浪与力聚合。原 Python 策略/观察模块采用对应独立验证方法，不能把全部 C++ 回调数量算作 Python 模块的全长覆盖。

本地替换 ROS Node/传输外壳，使用显式时钟与消息队列；不要求二进制与 Linux ROS 原程序相同。比较门保留原约定：位置 atol `1e-6 m`、速度 atol `1e-8 m/s`、角度 atol `1e-8 rad`；其余单位及相对容差见原评估。枚举、段号、布尔、ID/版本与事件顺序精确匹配。内部状态是比较器明确观测的字段集合，不声称穷尽所有隐藏变量。

## 判定

切换前 8010 使用 `original_gnc-proposal-full`，不是冻结原版。它与已验证 v8 构建的源文件指纹仅有三个文件不同：`coordinate_transform_node.cpp`、`ship_guidance_node.cpp`、`active_route_manager_node.cpp`。

| 补丁 | 相对原版的语义变化 |
|---|---|
| P-C1 | 区分普通/紧急避碰编码及速度上限作用范围 |
| P-C2 | 全路线弯道降速改成分段降速，并调整已通过顶点处理 |
| P-C3 | 减速可行性检查纳入实际执行速度 |

这些是行为修改，不是 ROS 外壳替换。原版保真成绩不能用来证明候选补丁与原版一致。

## 唯一产品基线

- 原始快照：`/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2`。
- 源清单 SHA256：`2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`。
- 已验证库 SHA256：`6e9f2728758b7934296e8da9bfee1a98905e038b29402c6e95ae780c6dc220fa`。
- 主 checkout 默认指针：`build/original_gnc-current`，指向既有 worktree 的 `build/original_gnc-glibc-v8`。没有复制或维护第二套 C++ 实现。
- 8010 launchd 的 `COLAV_ORIGINAL_GNC_BUILD` 使用主 checkout 默认指针。
- proposal-full 构建、补丁工具和旧 Run 保留为历史诊断证据，不再作为本次产品执行基线。显式指定其他构建的研究工具仍存在；未删除历史能力。
- 后续若改原 C++ 业务行为，应先更新唯一权威上游版本并重验，再更新集成；不能继续将本地语义补丁称为原版保真修复。

## 本轮验证

- 两个构建的动态库哈希均与各自 manifest 相符；逐文件比较确定上述三文件差异。
- 重新执行 `build/verify-original-delivery.py`：PASS。验证 230 个便携证据文件、325 个报告链接，以及 28 组/224 次模块回放的历史报告哈希链；这不是重跑全部长回放。
- 当前主 checkout + 原版库：原生生命周期、产品 adapter、资格和比较器测试 58 passed；路线接纳/拼接测试 28 passed，合计 86 passed。
- 当前比较器重新执行独立原端参考向量：基础六模块 10,315 回调、环境 12,992 回调、路线边界 43 回调通过，合计 23,350 回调。
- 8010 重启后 API 核实 `available=true`、`execution_lane=baseline`、`proposal_ids=[]`，库 SHA 与上述原版库一致。新 OT Run `5e27705c-5242-46e3-858e-20da82862cac` 的实际原生实例记录相同哈希、无 proposal 标记；保持 CREATED，尚未开始场景验收。
- 以上支持原 C++ 业务模块在已测同输入条件下保真；不证明原生 ROS 异步执行与本地调度在所有情况下轨迹一致，也不证明 OT 安全、速度性能或 D3 已通过。

## 旧 Run

`e9d40929-b619-4620-b75f-5c1c077d64b9` 保留候选库身份，759 帧，可信时间 0–379s。提前结束后的回放状态为 `INCOMPLETE/SESSION_REPLACED`，可播放可信前缀；不能标成完整成功运行，也不能改写成原版库 Run。

本轮过程、部署配置备份、测试日志及比较 JSON：`tmp/gnc_original_alignment_20260914/`。既有保真边界详见 [原评估报告](2026-09-10-original-gnc-fidelity-report.md)。

## 可留存证据

报告交付时将关键结果保存至文档目录，避免只依赖 tmp：

- [证据哈希清单](evidence/original-gnc-alignment-20260914/manifest.json)
- [构建差异与回调统计](evidence/original-gnc-alignment-20260914/alignment.json)
- [逐模块比较结果及比较器身份](evidence/original-gnc-alignment-20260914/vector-results.json)
- [58项回归日志](evidence/original-gnc-alignment-20260914/tests.log)；[28项路线回归日志](evidence/original-gnc-alignment-20260914/route-tests.log)
- [报告交付时的 API 状态](evidence/original-gnc-alignment-20260914/live-verification.json)
- [新 Run 实际原生实例身份](evidence/original-gnc-alignment-20260914/new-run-identity.json)

上述日志来自前一步已经完成的测试，本次报告整理未重复运行。API 身份则在本次交付时重新核验。历史完整证据仍以原评估的源 trace → 独立参考 → 嵌入版哈希链为准。

## 前端避碰验收清单

入口：<http://127.0.0.1:8010/>。当前原版 OT Run：`5e27705c-5242-46e3-858e-20da82862cac`，报告交付时为 CREATED、T=0。可直接开始；如需其他组合，在 Config 创建新 Run。

1. 确认 Original GNC 卡片说明包含 `baseline`，库哈希以 `6e9f2728` 开头；首轮 Environment OFF，保留当前种子与参数。不要将旧候选 Run 与新原版 Run 混为同一测试。
2. 先验当前 VO / Rule13 Overtaking。记录启动、首次速度异常、首次避碰路线接纳、明显转向、通过目标、恢复航线与到达终点的仿真时刻。通过目标与恢复航线须分别观察。
3. 航速分开核对：任务速度、planner 选定速度、GNC 最终设定、实际船速。当前任务为本船 8m/s（15.55kn）、目标船约5kn；不能用实际速度单独判断 planner 是否下达减速。若页面缺少某层信息，记录 Run ID 与时间，由原始证据补查。
4. 区分 planner 求解成功、adapter 提交、GNC 接纳、实际执行。路线被拒绝、降级或延后，应保留原始原因；不能仅凭绘制预测线认定已执行避碰。
5. 观察超越进度、持续低速、反复加减速、左右反复转向、清障后恢复与目标到达。每项异常均记录起止时间，而非只截一帧。
6. Results/Evidence 分列本船碰撞/搁浅、目标船碰撞/搁浅、COLREG行为、目标到达、航线恢复，以及真实 solver/fallback 状态。没有证据的项标记未验证，不从运行结束推定通过。
7. 完成当前 OT 后再测试对遇、交叉让路/直航，以及其他算法；Environment ON 单独一轮。一次只改变一个主要条件，避免无法归因。

异常反馈模板：

```text
Run ID：
算法 / 场景 / 环境：
异常仿真时段：
期望行为：
实际行为：
截图或回放位置：
界面显示的速度指令、实际速度、路线接纳/降级原因（如有）：
```

本轮对齐不保证先前航速波动消失。若原版重现，下一步根据同一 Run 的输入、接纳反馈和执行参考判断问题属于原版、adapter 或避碰算法；不直接改原 C++ 来使场景通过。
