# GNC卡片与第三工作面回放：main整合交接

## 本次范围

本对话的两项核心功能均纳入Simulator的main：

- GNC Stack新增的 **Authoritative GNC · 2026-09-14** 卡片及完整接入。VO/Fan走原生航迹向/SOG意图，Mid走原生航线；GNC仍负责控制、执行器及水动力。
- 第三工作面 **Evaluation** 的完整回放实现，包括已封存运行、播放/暂停、定位/步进、事件、Results/Evidence和独立回放海图。此次保留实现与既有回归，不将其宣称为用户已完成UI验收；后续新对话专门验证、优化回放。

相关提交：`45e274c9`（GNC与封存回放可核实）、`59813124`（回放海图隔离）、`bb6e36aa`（前端就绪证据）、`85d45eb0`（权威GNC原生输入）、`8c8659a8`（监控与机动分离）、`02d1b251`（本轮UI收敛）。

## 11条UI意见处理

| 意见 | 处理 |
|---|---|
| 1、2 | 移除倍率按钮前的SIMULATION RATE及后方最近/请求倍率文字；保留1×/2×/5×控制和无障碍名称。Replay Speed控件不变。 |
| 3 | 以SENSOR/COMPASS标题为基准。 |
| 4—10 | ROLL、WIND、WAVES、CURRENT、PROPULSION、CONSTRAINTS、GNC EXECUTION统一为10px、650字重、16px行高、6px/12px内边距、左对齐及1px底部分隔线。 |
| 11 | 卡片短说明改为 `Native C++ · course / route input.`；详细模块及来源说明保留在下方。 |

CSS与app.js资源版本均更新，避免浏览器继续使用旧缓存。浏览器已核对11个卡片标题的实际computed style；新进程隔离预览已核对短说明。没有操作用户暂停的仿真进度。

## 验证

- 前端：`node --test tests/web_gui/*.test.mjs`，**325 passed**。
- 合并后main：GNC产品与回放API/capture/playback/window/event/evidence相关pytest，**119 passed**，85.51s。显式指定已验证v5原生构建；1项现有Starlette弃用提示。
- JS语法检查、修改Python文件Ruff及`git diff --check`通过。
- 先前VO修复的158项测试和4个完整闭环证据见 [监控/机动修复报告](2026-09-15-vo-monitoring-maneuver-admission-fix.md)，本轮未重复算法调参与闭环验收。

## main原有改动保护

合并前main的4个已修改文件和3个重叠未跟踪文件已完整备份：
`/Users/marine/Code/.worktrees/Colav-Simulator/gnc-avoidance-contract/tmp/gnc_execution/main-merge-backup-20260915-145358/`。

另保留定向stash `7c46b2a3505376d9b074d797083f356d3d9b2032`。这些早期路线中转修复、测试和规格已被当前原生输入方案覆盖，不再重新套用到新main；其余未跟踪诊断材料保持原地。

## 运行环境与下一轮

本轮是代码整合与推送，不重启8010/8020，不更换现有Run的原生库。

权威GNC仍在独立本地仓库 `/Users/marine/Code/GNC`，提交 `b3b7b2b`；该仓库没有配置远端，不在本次Simulator推送范围内。源清单及本地编译产物是运行依赖，Simulator推送不包含整个GNC源码平台或二进制。

已验证构建：`/Users/marine/Code/.worktrees/Colav-Simulator/gnc-avoidance-contract/build/gnc-velocity-v5`。主checkout旧默认构建指针未切换；启动新main进程前，显式设置 `COLAV_ORIGINAL_GNC_SOURCE=/Users/marine/Code/GNC` 和 `COLAV_ORIGINAL_GNC_BUILD` 为该构建，或按 `cpp/original_gnc/README.md` 在main重建后切换指针。不要把旧运行记录改写成新库身份。

下一轮优先从Evaluation回放已封存Run验证：连续播放与倍率、暂停定位和步进、事件同步、独立海图、GNC遥测及缺失字段、Results/Evidence身份，以及回放操作不改变Active Session。保留旧/新GNC Run各自记录的来源身份。
