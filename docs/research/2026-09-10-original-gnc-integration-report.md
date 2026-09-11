# 原版 GNC 避碰集成报告
24 格产品入口真实运行完成：3 格运行至结束，21 格失败；2 格硬安全通过，0 格同时任务完成与硬安全通过。场景适配验收失败；不能宣称避碰能力已可用。
## 实现与身份
冻结源：`/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2`，183 个清单文件核验通过。清单 SHA256：`2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`。

工作区：`/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration`；分支 `codex/original-gnc-integration`；基线 `31558544ec88f77941481226da7f3c1c10d1674d`。本轮未提交、未合并。原主工作区及 8010 服务未作为测试实例。

最终嵌入库：`build/original_gnc-glibc-v8/liboriginal_gnc-0be0028f097d440abb34242feac84040.dylib`；SHA256 `6e9f2728758b7934296e8da9bfee1a98905e038b29402c6e95ae780c6dc220fa`。默认 `build/original_gnc-current` 指向该构建。完整编译参数、依赖、导出符号及提取身份见 [构建清单](../../build/original_gnc-glibc-v8/build-manifest.json)。
产品新增独立原版 GNC 开关组合：环境 OFF 执行 6 个原 C++ 核心加 4 个原 Python 策略/观察器；ON 再执行 4 个原 C++ 环境模块。原船体是本船唯一积分来源，原聚合器是本船唯一环境载荷来源；航线经过原仲裁、坐标/几何检查、导引、控制、分配和执行器。旧 FCB Full 后端保留。24 格均记录 `fallback_used=false`。

VO/Fan 的规划速度语义为 SOG，传入原接口后为路线速度上限；方向是北东平面的路径方位及原方位一致性检查，不直接当作对水航速、实船艏向或舵角。Mid 保留已接纳的命令速度标签，预测几何作为路线，不逐帧强制艏向。环境下这套转换的可执行性仍未通过资格验收。

框架北东坐标经 RouteFrame 转为原 WGS84 合同：首个名义点对应源参考原点 58°N、6°E。原 GeoPosition 属于这个显式参考框架；界面地理位置由框架世界坐标生成。

VO/Fan 的 120 m 固定锚点依据原 60 m lookahead，未拉长路径规避 500 m 首变化点保护。Mid 80×5 s 预测需先通过既有 L4 接纳。三者不复用旧 Full 能力证书。实际测得原版近似 course tau 73.487 s（R² 0.941）、speed tau 29.620 s（R² 0.344），仍标 `UNQUALIFIED_FIRST_ORDER_APPROXIMATION`，没有伪造 trackability 资格。

## 关键不兼容

- 所有 24 格，原坐标模块接受的避碰 plan ID 数量均为 0。 独立[全事件审计](evidence/original-gnc-20260910/route-admission-audit.json)不按请求 ID 过滤，结果仍相同；接受类型仅为 nominal/internal_return_to_route，序列 0..N−1 完整。部分请求由 manager 转发后被原几何/频率门拒绝；“桥接发布”“manager 转发”“coordinate 接受”“执行避碰”四者不可混写。
- VO 六个单船会遇格因真实规划不可行失败。两个多船格运行 1800.1 s，硬安全通过，但未满足任务终点/恢复窗。内部 `stop_nonpaper_wrapper` 是不可行候选标签，桥接拒绝发布；没有作为执行 fallback。
- Fan 七格因 `NoContinuouslyFootprintSafeTrajectory` 失败；CS-E4 到达框架 goal，但最小船体净距 15.921 m，小于 50 m 硬门，安全失败。
- Mid 八格均真实执行 IPOPT，随后在仿真 t=0 被 `TRACKABILITY_CAPABILITY_TUPLE` / `INCOMPLETE` 拒绝。不可依据失败摘要的 `solver_executed=false` 写成未求解：不可变 solver artifact 有正迭代数、真实求解状态和质量字段。旧 CustomMPCAdapter 对失败的该汇总标志存在语义不一致，未为通过测试改写。Fan 终态同类标志也需结合实际候选数和 solve ID。

## 24 格结果

失败格评估未完成标“未评估”，不把聚合 fail-closed 标签当作已测到碰撞。运行结束也不等于 goal 到达。所有格原避碰计划接受数均为 0。

| Case | 运行结果 | 仿真 s | 原 manager 转发 ID | 硬安全 | 最小船体净距 m | 框架 goal | 证据 |
|---|---|---:|---:|---|---:|---|---|
| vo-head_on-E0 | FAILED | 191.0 | 28 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/vo-head_on-E0/66445ec7-007e-4261-a5a3-f21e32e7a9bd/manifest.json) |
| vo-crossing_give_way-E0 | FAILED | 122.0 | 30 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/vo-crossing_give_way-E0/3185a447-61bb-4d2a-b559-7bf074d14d0d/manifest.json) |
| vo-overtaking-E0 | FAILED | 247.0 | 15 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/vo-overtaking-E0/1e667399-a141-45a1-92c7-de91ba35f35e/manifest.json) |
| vo-paper_ccta2023_multiship-E0 | COMPLETED | 1800.1 | 2 | PASS | 655.824 | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/vo-paper_ccta2023_multiship-E0/4f2c4ad0-4496-4682-ab3f-b4a24be1f979/manifest.json) |
| potocnik_colreg_fan_mpc-head_on-E0 | FAILED | 195.0 | 67 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/potocnik_colreg_fan_mpc-head_on-E0/a11c4c34-cd8e-4566-a54f-0024e787255f/manifest.json) |
| potocnik_colreg_fan_mpc-crossing_give_way-E0 | FAILED | 145.0 | 58 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/potocnik_colreg_fan_mpc-crossing_give_way-E0/b14316bb-9f31-4b1b-ab45-1f86ee3e2417/manifest.json) |
| potocnik_colreg_fan_mpc-overtaking-E0 | FAILED | 265.0 | 92 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/potocnik_colreg_fan_mpc-overtaking-E0/97766dd3-7697-4434-8abe-2a8a9d18ec16/manifest.json) |
| potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E0 | FAILED | 1455.0 | 466 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E0/37ea82b7-faa1-4e57-a51e-11d4dbdeab63/manifest.json) |
| mid_mpc_ipopt-head_on-E0 | FAILED | 0.0 | 0 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/mid_mpc_ipopt-head_on-E0/87d9b9a2-2117-4509-881b-8376c262785c/manifest.json) |
| mid_mpc_ipopt-crossing_give_way-E0 | FAILED | 0.0 | 0 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/mid_mpc_ipopt-crossing_give_way-E0/392b76dc-30e3-4a9f-bbb3-b904f89227bf/manifest.json) |
| mid_mpc_ipopt-overtaking-E0 | FAILED | 0.0 | 0 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/mid_mpc_ipopt-overtaking-E0/d501c498-b965-4b3b-875a-9ba37e7314a0/manifest.json) |
| mid_mpc_ipopt-paper_ccta2023_multiship-E0 | FAILED | 0.0 | 0 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/mid_mpc_ipopt-paper_ccta2023_multiship-E0/7e1824eb-83fe-4bc4-b668-ca43fef06715/manifest.json) |
| vo-head_on-E4 | FAILED | 174.0 | 28 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/vo-head_on-E4/3d7606df-f6f6-4163-bc9a-f7e5ec0d5380/manifest.json) |
| vo-crossing_give_way-E4 | FAILED | 130.0 | 24 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/vo-crossing_give_way-E4/33f0720d-5857-4d7b-8c59-33311b0102ba/manifest.json) |
| vo-overtaking-E4 | FAILED | 380.0 | 22 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/vo-overtaking-E4/97565a05-48fe-4df1-bca2-44ff8e1b457b/manifest.json) |
| vo-paper_ccta2023_multiship-E4 | COMPLETED | 1800.1 | 200 | PASS | 677.811 | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/vo-paper_ccta2023_multiship-E4/10c914aa-27e2-4814-93c4-2363e149e35c/manifest.json) |
| potocnik_colreg_fan_mpc-head_on-E4 | FAILED | 195.0 | 77 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/potocnik_colreg_fan_mpc-head_on-E4/2b2dc320-3d81-45e3-962e-e94eb23ce3a8/manifest.json) |
| potocnik_colreg_fan_mpc-crossing_give_way-E4 | COMPLETED | 271.5 | 108 | FAIL | 15.921 | True | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/potocnik_colreg_fan_mpc-crossing_give_way-E4/00429c75-31f5-4d73-aba1-b2ee17d5b225/manifest.json) |
| potocnik_colreg_fan_mpc-overtaking-E4 | FAILED | 335.0 | 131 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/potocnik_colreg_fan_mpc-overtaking-E4/5f60d43a-962c-4522-a3d4-fc5f4c0d8648/manifest.json) |
| potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E4 | FAILED | 1415.0 | 491 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E4/2798bf65-f64c-4470-831f-a667396a6be3/manifest.json) |
| mid_mpc_ipopt-head_on-E4 | FAILED | 0.0 | 0 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/mid_mpc_ipopt-head_on-E4/e343d98b-d1a8-444f-9aae-0fff6610d411/manifest.json) |
| mid_mpc_ipopt-crossing_give_way-E4 | FAILED | 0.0 | 0 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/mid_mpc_ipopt-crossing_give_way-E4/86179352-bb2a-4f0c-bbf2-15a4df8fa8cc/manifest.json) |
| mid_mpc_ipopt-overtaking-E4 | FAILED | 0.0 | 0 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/mid_mpc_ipopt-overtaking-E4/49234568-fb4a-4324-a78a-25637f0def38/manifest.json) |
| mid_mpc_ipopt-paper_ccta2023_multiship-E4 | FAILED | 0.0 | 0 | 未评估 | — | False | [运行](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-campaign-final-05/mid_mpc_ipopt-paper_ccta2023_multiship-E4/fd34f994-fe82-4023-b50c-91849a750d5f/manifest.json) |

[24 格完整结构化审计](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/product-acceptance-summary-v2.json) 包括拒绝原因计数、实际求解 artifact、全船/本船安全、COLREG 原始分值、voyage、逐文件 SHA256 与规划耗时。
## 安全、行为与实时口径

VO 两个多船完成格，本船/全局碰撞和搁浅计数均 0，最小船体净距分别 655.824 m、677.811 m；这只证明这两次固定窗口硬安全，不是避碰路线已被原 GNC 执行，也不是全部 COLREG 规则或论文复现通过。失败的 21 格没有完整 G3 评估，不补零。

实际规划耗时按 Parquet 中唯一成功 solve ID 去重，给最大/中位/P95；终止调用单列。该时间包含规划 API 与接纳检查，不是仅 IPOPT 优化器耗时。VO 实际内部周期 1 s，即便 RunSpec 记录 5 s；Fan 5 s，Mid 只有初次真实调用。总 wall 包含 ENC/序列化/I/O，不作为控制循环硬实时保证。

名义航线通过原执行链，避碰活动线在接纳前失败，因此未形成可验收的活动避碰线跟踪和恢复阶段。原 GNC 末端、框架 goal 与统一位置/速度判据分别保留，不能互替。原生 ROS2 端 24 格自主算法闭环和“已接受避碰计划”的双端回放没有完成：当前产品格没有原坐标模块接受的避碰计划，先被合同兼容问题阻断；不能用 L4 合成边界向量冒充实际算法接受计划。

## UI 与回归

独立服务 [8014](http://127.0.0.1:8014)。真实浏览器 OFF/ON 各运行 20 s 至 FINISHED，模块数分别 10/14；OFF 环境合力为零，ON 非零，均无 fallback，动态库 SHA 与最终候选一致。创建时异步目录刷新竞态已修复：fetch 返回后再次检查 creating。延迟 Promise 行为测试及真实重新创建通过；复验起点后无新增控制台错误，历史错误保留。

- [UI ON](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/ui-evidence/on-session.json)；[UI OFF](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/ui-evidence/off-session.json)；[竞态复验](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original_gnc-glibc-v8/ui-evidence/creation-race-fixed-console.json)。
- [原版 focused 80 passed](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original-v8-focused-regression.log)；[UI 100 passed](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original-ui-creation-regression-02.log)。
- [GNC 扩展回归 773 passed / 1 skipped / 7 failed](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original-v8-gnc-regression.log)；[同 7 例干净基线复现](/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration/build/original-baseline-regression-comparison.json)。
七个失败在干净基线 31558544 逐一复现：Mid stack-B OT XTE 53.5507>50；VO HO crossing 计数 5>2（两项）；VO OT 3>2；Mid OT QUALITY_RECOVERY_SUFFIX；Mid HO SAFETY_SWEPT_CLEARANCE；planner audit Mid INFEASIBLE。当前运行未观察到这组测试新增失败；不能写全套或 CI 全绿。

## 下一步决策边界

当前交付是独立后端及失败可追溯的兼容性验收。进一步可用化需单独设计：VO/Fan 短期意图与原 500 m/10 s/侧偏保护的路线合同、Mid 原版动力学能力资格、以及原 GNC 本身转弯/末端性能。任何修改几何、原保护或控制增益均超出本轮冻结保真范围；不能以关闭门槛实现“通过”。
