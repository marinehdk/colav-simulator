# 已掌握会话推进与船舶状态推进的边界

用户已能准确区分：`SimulationSession.advance()` 包装一次完整仿真步，覆盖全部活动船的 tracking、planning、forward 及会话事件；`Ship.forward()` 只负责把 references 经过控制器和船舶模型变成下一状态。该边界已掌握，后续可进入 `Ship` 内部数据契约。

## Evidence

用户在纠正后独立复述了两个方法的不同职责。

