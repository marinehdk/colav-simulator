# 已掌握主数据流，需校准会话生命周期

Status: superseded by LR-0002

用户已能正确识别 `track -> plan -> 船舶状态更新 -> 前端绘制` 主方向，并知道 `Ship.plan()` 是避碰算法进入闭环的关键位置。下一阶段需巩固两个边界：`WebSessionManager.tick()` 不创建会话，而是推进已创建会话；`SimulationSession.advance()` 包装整个仿真步，真正推进船舶动力学的是 `Ship.forward()`。

## Evidence

用户能独立口述从 Web 控制到算法、动力学和浏览器显示的整体链路。
