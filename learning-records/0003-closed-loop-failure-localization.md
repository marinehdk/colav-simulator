# 能从闭环而非单看规划器定位风险

用户已能指出：即使规划预测看起来合理，低层控制无法跟踪、船舶模型参数错误或数值积分问题仍会让真实状态偏离并发生碰撞。这表明已掌握跨 planner、controller、model 边界诊断的基本方法；下一步需严格区分 predicted trajectory、control reference 与真实 state。

## Evidence

用户独立给出了控制执行与模型/积分两个不同子系统的失败来源。

