# GNC 与封存回放：前端验收交付

日期：2026-09-14。状态：**前端功能可验收；Original GNC 仍为诊断候选，D3 未通过。**

实现提交：`45e274c9`、`59813124`。本次未修改冻结 C++、外部原始源码、MPC 模型或避碰算法/安全阈值。8010 已实际加载并运行候选库；8014 保留。

## 可以如何验收

入口：<http://127.0.0.1:8010>。

1. Config → Rule 14 / Head-on → Fan-MPC / Truth → Original GNC → Environment OFF。GNC 描述应明确显示 candidate、P-C1/P-C2/P-C3，说明区可核对 library SHA256。
2. Parameters 的 Solve period 可填 `5`；真实键盘删除后为空并在合同中显示 `null`；`0` 阻止 Create。空值沿用算法默认。点击 Create 后保持 CREATED，再到 Deployment 启动。
3. Evaluation → Replay，优先打开 `8a0312a3`：这是本次从真实 Config 提交、实际运行至目标的新 Run。观察 SEALED/HISTORICAL、FULL、海图和船舶，测试任意 seek、20×、暂停、自然结束、重播、事件过滤与跳转。
4. Results/Evidence 必须保持同一 Run 身份，显示 `DIAGNOSTIC ONLY`、诊断原因、Original GNC stack/library hash。本船安全、全船计数、任务到达分别看。
5. 打开 `20fc2c2c`：应显示 FAILED、INCOMPLETE、可信截至 305.0 s，能查看611帧前缀；Results 显示数值失败，不伪装完整安全验收。
6. Historical AIS → Historical Replay → Run Historical Workflow → Open Replay。已实测的 `720d0e15` 是600帧、4艘船、带封存ENC的共享播放器样例。Counterfactual 的预测资格未在本轮升级。

## 实际联验 Run

| Run | 配置/结果 | 回放与证据 |
| --- | --- | --- |
| `8a0312a3-4f5a-49d2-a4ea-91834d535e91` | 真实前端创建，Fan / Head-on / E0 / 显式5 s；1086 s到达目标；本船硬门PASS，最小净距384.8699 m；全船碰撞/搁浅均0；无fallback | READY/FULL，2172帧；封存文件读取前后不变 |
| `550583ab-f406-4d59-adbc-9406a1654d54` | 产品API，Mid / Crossing GW / E0 / 诊断配置5 s；1200 s结束、本船硬门PASS、净距819.5127 m；未到达目标；全船搁浅1 | READY/FULL，2400帧；实测首窗口约1532 ms，中/晚窗口约16/11 ms；封存文件不变 |
| `20fc2c2c-9fba-481d-ad29-5ecf594951c8` | 产品API，Mid / Head-on / E0 / 5 s；NUMERICAL_FAILURE | FAILED + INCOMPLETE，611帧，0–305 s可信前缀；越界读取拒绝；失败原因、诊断身份可见 |
| `720d0e15-a2fb-4cd8-8e4a-a6c50d404867` | 真实HAIS按钮，Historical Replay工作流 `501a3a04-6ce4-48e4-9bde-823a79c1288f` 完成；4艘批准runtime actors；无fallback | READY/FULL，600帧，60–659 s；enc.png/static_context.json均保存；早/中/晚读取文件不变，暖窗口约2.5–3 ms |
| `e5f68ad4-a47a-41ce-91a8-d22e37a7e28c` | 旧Mid录制兼容性样例，无Original GNC绑定 | FULL/1821仍可读；不作为两功能联合运行证据 |

以上延迟为少量端到端抽样，不是P95基准。Replay的倍速属于呈现时钟，不能代替仿真求解吞吐量。

`8f3a1748-cf01-48cf-bde7-1d8e6e056154` 保留为先前10 s周期的Mid交叉失败样例：29.5 s失败、60帧前缀。它与5 s矩阵不是同配置。

## 新24格诊断矩阵

完整执行与汇总命令已返回 **exit 0**：3规划器 × 4场景 × Original环境OFF/ON，seed 0。

- 18格完成并通过本船硬门，6格运行失败；4格达到任务目标。
- 已完成18格：本船碰撞/搁浅均0；全船碰撞均0，**6格各有1次目标船搁浅**。不据此声称全船安全通过；失败6格不计为完整安全评估。
- COLREG v2只统计18个已完成且已评估的格，共23个遭遇：17 COMPLIANT、6 PARTIAL、0 NON_COMPLIANT。属于本地行为重建评分，不等于正式合规，也不是24格全COMPLIANT。
- Mid六格失败：HO-E0与MS-E0/E4为优化器NUMERICAL_FAILURE；HO-E4为优化器INFEASIBLE；OT-E0/E4是L4候选拒绝（SAFETY_SWEPT_CLEARANCE，E4另有QUALITY_CPA_RELEASE）。后两格的粗粒度PlanStatus虽为INFEASIBLE，不能误归因成优化器无解。

逐格表：[matrix.md](2026-09-14-gnc-replay-matrix.md)。结构化真相：[matrix.json](2026-09-14-gnc-replay-matrix.json)。已完成格评分：[colreg.json](2026-09-14-gnc-replay-colreg.json)。执行文件哈希：[runtime-files.json](2026-09-14-gnc-replay-runtime-files.json)。

矩阵开始于 `84fa2252` 加本轮GNC修复的工作树；期间核对74个规划器/GNC/配置文件，结束时**无哈希漂移**。之后的本地提交保存同一执行代码。Run内原有commit/dirty记录未改写；既存未跟踪文件仍保留。矩阵不是在伪造的“干净最终commit”上运行。

矩阵使用已记录诊断配置：Mid的CPA safe/hard为150/50 m、求解周期5 s。前端默认产品profile为200/180 m，默认周期来自算法；本轮只新增可选周期传递，**未改变默认安全参数**。不得把矩阵18/24直接套到另一套前端参数。

## 本轮测试与修复

| 验证范围 | 实际结果 |
| --- | --- |
| Replay七个Python文件（含断连捕获、索引/帧序/时间/摘要、前缀、预算、只读边界、线程绘图） | 109 passed；1条依赖弃用warning |
| 全部前端Node测试 | 324 passed，0 fail/skip |
| Original GNC七文件，baseline原生库 | 86 passed，0 skipped |
| Original GNC七文件，proposal-full原生库 | 86 passed，0 skipped |
| Config API参数门 | 10 passed；有限正数与默认None覆盖 |
| Historical API/catalog focused | 30 passed / 2 optional skips；真实HAIS与静态捕获另行通过，并完成上表真实浏览器执行 |
| 修改Python文件Ruff / git diff check | 通过 |

没有把上述focused结果说成仓库全量pytest或远端CI绿色。未重跑历史70格保真/28组源输入回放；它们的证据仍只约束原报告对应的baseline库。

实际修复包括：

- 原生build批准源绑定、candidate身份、诊断资格透传；可选solve period从Config到RunSpec。
- 统一Replay模块实例和打开按钮；实际ENC字段适配、首帧交通视野、事件定位、播放状态、异步结果竞争、1440×900布局。
- 帧序/时间/index/digest验真，损坏gzip与非对象index的typed降级；可信前缀与事件范围一致，活跃捕获不能冒充封存读取。
- event journal计入捕获预算；只读查询不等待无关求解器全局锁；内存旧READY不能覆盖磁盘完整性失败。
- HAIS使用批准的4艘runtime actors，在生产端保存ENC/context；离屏FigureCanvasAgg不依赖Visualizer选择的全局GUI backend。

## 构建身份与运行边界

当前8010的launchd配置显式指定：

```text
COLAV_ORIGINAL_GNC_BUILD=/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-proposal-full
```

候选库SHA256：`6da7998cf7ec55dedb4a8fe493478b40522e6c7e272a3706297ac84fc5c5069f`。
批准source manifest：`2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`。
原版baseline库SHA256：`6e9f2728758b7934296e8da9bfee1a98905e038b29402c6e95ae780c6dc220fa`。

Original运行保持 `diagnostic_only=true`。任务到达、COLREG行为和Mid失败项仍未达到D3；不以移除保护门、fallback或改变评分阈值换取通过。

## 本机证据位置

完整输出在 `tmp/gnc_replay_acceptance_20260914/`，真实Run在主checkout的 `runs/`。

- `matrix24/` 与 `final-colreg/`：24格原始产物及独立评分。
- `replay-tests-final.log`、`frontend-tests-final.log`：完整focused命令输出。
- `final-ui-created.json`、`final-ui-session.json`、`verified-*.json`：真实请求/状态/只读检查。
- `hais-workflow-final.json`、`hais-final-verified.json`：最终工作流及封存验证（Run720d0e15）。
- `hais-replay-1440-final.png`、`failed-run-results-final.png`：真实浏览器截图。
- `frontend.plist.before`：部署前launchd配置备份。

失败Run的首次不可变性检查曾与评价异步归档竞争；测试工具随后等待最终FAILED manifest再检查，同一Run重验通过，未重执行。中途缺图/GUI后端阻塞的测试尝试保留，不包装为成功。
