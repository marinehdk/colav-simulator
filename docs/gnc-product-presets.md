# GNC Stack 产品预设

2026-09-09。仅调整产品预设、页面与新会话绑定，不改避碰算法或放宽执行门槛。

| 预设 | Plant | Guidance | Controller | Actuation | Environment |
|---|---|---|---|---|---|
| Legacy Without Modules | 场景原模型 | 场景原导引 | 场景原控制器 | 场景原执行链 | OFF |
| FCB 4DOF Ideal Actuation | FCB45 4DOF | Pass-through | FCB45 PID | 理想广义力 | OFF / ON |
| FCB Without Guidance | FCB45 4DOF | Pass-through | FCB45 PID | V2 分配与执行器动态 | OFF / ON |
| FCB Full Stack | FCB45 4DOF | ILOS | FCB45 PID | V2 分配与执行器动态 | OFF / ON |

FCB 预设共用同一套物理 V2 船体与控制器参数。4DOF 包含 surge、sway、roll、yaw，roll 不受主动控制。V2 执行链包含 3 主推、2 独立舵、2 低速首侧推及动态限制。理想执行保留 PID 输出限制。

## 接口与页面

`GET /api/gnc/stacks` 增加 `product_presets`：四个预设分别提供稳定的 ID、展示字段及 `variants.off/on` 对应的完整 stack ID。页面仅选择预设和环境开关，显示“选中字段”“四栈对照”两个只读表；完整模块参数、配置 hash、证据在可展开的技术详情中。

`POST /api/sessions` 继续使用现有 `gnc_stack_id`。六个 FCB 变体均可通过目录绑定。`legacy_without_modules` 为显式无模块静水预设，取消本船模块注入并关闭场景 stochasticity；旧的 null 绑定语义无需改变。新建页面默认该显式 Legacy 预设。

FCB OFF/ON 均关闭旧场景扰动源，由选中的模块环境成为本船唯一环境载荷来源。OFF 不装配环境；ON 绑定 `analytic_environment_field + fcb45_environmental_load`，风 NE=(6,2)m/s、流 NE=(0.4,-0.2)m/s、Hs=1m、Tp=7s，随机种子可复现。Legacy 不支持模块环境，开关禁用并说明原因。

Full 使用 accepted route 导引接口；其余 FCB 变体直接消费航向/速度参考。实际产品 route bridge 继续承担算法输出适配，不新增静默回退。

## 验证

- 目录、共同船体、ON/OFF 参数隔离、显式 Legacy 清除模块与扰动、六种 FCB 变体各 20s 实际模块执行。
- 七种组合均通过新建 Mid-MPC / head-on / God 会话及多步执行接口检查，验证实际 guidance、actuator、environment trace 与选择一致。Mid 使用原 qualified domain profile，不绕过原资格门槛。
- 预设测试含接口：15 passed；目录及环境目录联合测试：34 passed（包含其中8项，不重复累计）。最终扰动单源补充验证：8 passed。
- 前端测试：250 passed。Ruff check、改动范围 format check、git diff --check 通过。
- 8010 已加载新目录。浏览器验证四预设、ON/OFF、两张表及创建流程；从页面创建的 Full Stack / VO / head-on / OFF 会话通过三次单步执行。
- 证据：`tmp/gnc_presets_20260909/`。

验证范围为新会话装配、接口与短时实际执行；不等同于全部算法全场景任务到达验收。既有完整工程栈的 Mid-MPC OT / 多目标精停缺口不在本次修改范围内。
