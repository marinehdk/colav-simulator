# 外部算法集成证据

证据日期：2026-07-27。固定场景：`paper_ccta2023_multiship`，`t_end=0.2 s`，严格禁止回退。

| 集成 | 依赖身份 | 闭环结果 | 证据 |
|---|---|---|---|
| VIMMJIPDA | `b4a0f77ddf72dc8ffd66095418732996c14ea1eb` | 0.2 s `FINISHED`；真实 tracker 配置、量测和航迹进入统一帧 | run `faa51386-4025-435a-a98f-ac4c272797c6` |
| PSB-MPC | `367dad8809424b21c013512308de2a07bd184464` | 0.2 s `FINISHED`；真实 ENC polygons、3 个目标航迹、求解诊断 | run `18f56f06-1d10-4ab0-82c3-b201b2abb7cd` |
| RRT* | `9a661df7acba1bead09e6540f0b3988050db37b5` | 依赖和 hazard/CDT 接口可用；该固定场景无路径，显式 `INFEASIBLE`，无 LOS 冒充 | run `36ffcdd3-6d8d-45d9-9fc8-d7dc0231b1fd` |
| RLMPC | `73ef4b8cc3850a7a3b007ec14d18b962d134be34` | 依赖门失败：`No module named 'casadi'`；不可选择、不可伪成功 | manifest dependency status |
| 自研 MPC | `module:factory` | `ICOLAV` 插件入口、诊断和 manifest 契约已冻结；算法实现未提供 | `IntegrationRegistry._build_plugin` |

上述 VIMMJIPDA/PSB-MPC 证据只证明短烟测，不证明代表场景完整闭环。

PSB-MPC 在 `paper_ccta2023_head_on` 完整 500 s 审计中触发 Eigen
`Block.h:126` assertion，进程退出码 134。run
`70527617-5353-4c9e-9424-e49de9a28bc8` 只留下 `CREATED` manifest；原生
abort 未能生成完整失败证据。

正常完成或 Python 可捕获失败的 run 目录采用相同六件证据包：
`manifest.json`、`episode.json`、`trajectory.parquet`、`events.jsonl`、
`evaluation.json`、`report.html`。RRT 的可捕获失败样本保留完整证据。

## 尚未通过

- RRT* 固定论文场景闭环门。
- RRT 专项 `rrt_test` 当前在场景生成阶段报 `Polygon is empty`。
- PSB-MPC 完整场景稳定性和原生进程隔离门。
- RLMPC 依赖/求解器门。
- 自研 MPC 算法闭环和基准矩阵。
- 官方 Evaluator 数值门。
