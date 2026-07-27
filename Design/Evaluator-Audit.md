# Evaluator 来源审计

## 结论

- 本地框架仓库、四个依赖仓库未发现论文官方 Evaluator 源码、可执行工具或许可证文件。
- 当前 `Evaluator` 为公共接口先行的重建实现，不是官方数值实现。
- 输出固定标记 `functional_reproduction` 和 `numerical_reproduction_confirmed=false`。
- 官方实现到位后，只允许替换 `Evaluator.evaluate(...)` 后端；上层证据格式、Web、批量接口不变。

## 已实现范围

- 时间轴对齐、CPA/TCPA、最小距离、碰撞和搁浅检测。
- `clear/head_on/crossing_give_way/crossing_stand_on/overtaking` 遭遇分类。
- Rule 8、13、14、15、16、17 对应字段。
- 操纵幅度、操纵提前量、风险、延误、逐船搁浅裕度、逐船对和聚合结果。
- 无重叠时间、短轨迹、无 ENC 等异常输入显式告警。

## 数值禁区

- 未从 Table I/II 反推或拟合公式。
- 未取得论文原始场景参数、官方 Evaluator、阈值和舍入流程。
- 当前分数仅用于验证数据闭环、接口和相对比较，不得宣称论文数值复现。

## 后续数值门

1. 取得官方工具及可用许可证。
2. 固定工具版本、源码 SHA、运行环境和阈值。
3. 用同一 `episode.json` 输入官方与重建后端。
4. 对齐遭遇阶段、船对选择和搁浅补偿。
5. Table I/II 两位小数全部一致后，才允许标记 `numerical_reproduction`。
