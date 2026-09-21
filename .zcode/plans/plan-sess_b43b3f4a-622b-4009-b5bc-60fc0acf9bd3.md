# Config 第 4 步 GNC Stack：四轴保真度阶梯卡片 + 组合解读 + Create 绑定（Phase 1 静水）

## 目标
Assembly Steps 变 5 步：04 GNC Stack（四轴正交卡片，保真度阶梯排序）、05 Parameters。GNC 选择进 create 契约：默认 Legacy（场景原动力学，零行为变化），选 modular 栈则本船切 `build_modular_ship_adapter`。环境轴预留、锁"静水"，V2 另立 ticket 接风浪流。

## 后端

1. **catalog 加 `module_axes` 键**（additive，schema 仍 v1，`colav_simulator/modular_gnc/catalog.py`）：每轴可选模块清单，每项含 `identity / display_name / tier`（阶梯序，简→繁）/ `models`（该模块考虑了什么）/ `expected_effect`（预期影响文案）/ 布置类模块加 `drive_nature`（欠/全/过驱动）。文案后端 authored、诚实不 overclaim（mock 资产如实标注）。阶梯：Plant Legacy→Kinematic→3DOF→Roll-4DOF；Guidance/Controller 直通→功能模块；Actuation None→分配器→+resolved（布置三卡同级）。
2. **create 契约**：`gui_server/main.py` `SessionCreateRequest`（:206-220）加 `gnc_stack_id: str | None = None`；`RunSpec`（`experiment/contracts.py:74`）加 `ownship_gnc_stack_id: str | None`。校验：未知 stack_id → 422；historical/replay 场景带栈 → 422 拒绝。
3. **runner 注入**：`experiment/runner.py` `_prepare` 配置加载后（override 合并后）注入：栈 id → `list_stack_catalog()` 反查 config dict → `normalize_ship_modules` → `config.ship_list[0].ship_modules`。telemetry `modular_gnc` 键链路已有。
4. **dt/seed 修复**：`build_ship`→`factory.build_modular_ship_adapter` 传场景 `dt_sim`/episode seed 到 `ModularShipStack.from_config`（现默认 0.1/0；栈 dt 必须等于仿真 dt），测试锁定。

## 前端（web_gui）

5. **stepper 4→5 步**：`index.html` :37-43 加 `data-config-step="gnc"` 按钮（04，`configStepGncState`），Parameters 改 05、面板徽章重编号；`config-shell.js` `renderStepper`（:717-736）加 gnc 步（完成=任何选择含 Legacy 默认）、`of 5 ready`、`readyCount * 20%`；`style.css` :413/:747 同步。
6. **第 4 步面板重建**（index.html :202-226 + config-shell.js :804-862 + style.css :482-494）：删 64 项 `<select>`，五组卡片（复用 `makeChoiceCard`/choice-grid，参照 Algorithms 步）：
   - Plant（4 卡，阶梯序）：Legacy / Kinematic / 3DOF / Roll-4DOF；选 Legacy → `gnc_stack_id=None` 其余轴置灰；
   - Guidance（2）、Controller（2）：直通在前；
   - Actuation：None → 3 布置（同级，标驱动性质）+ Resolved 开关；
   - Environment：锁定卡"静水 (default) · V2 风浪流"。
   - 每卡带后端 `models` 一行；卡序由 `tier` 定，客户端不硬编码。
   - **组合解读条**（新增，evidence 上方）：选完 4 轴显示"该组合考虑了什么"（拼接选中模块 models）+ `expected_effect` 后果文案 + fidelity/acceptance/asset trust 既有字段；Legacy 显示"scenario default dynamics"。
   - 组合→栈匹配按各栈 `modules[]` role/identity/参数；catalog 无该组合 → 卡禁用 + "backend catalog 未提供该组合"。下方保留 #60 Stack Evidence 四组字段。
7. **draft 接线**：`gnc_stack_id` 进 draft（默认 None）；Create body 携带；Config Summary / YAML contract 加 GNC 行；step 小字显示 Legacy 或栈短名。

## 测试

8. Python：`tests/test_gnc_stack_api.py` 扩展（module_axes 含 tier/models/effect、create 绑定/未知 422/historical 422/默认 None 零变化）+ runner 注入 + factory dt/seed。
9. Node：`config-shell-static.test.mjs`（5 步断言、×20%）、`gnc-stack-static.test.mjs`（卡片结构、零客户端校验/零硬编码模块身份断言保留、新增解读条与 draft 断言）。
10. 验证门：pytest 全套（基线 1432/9/3 + 新增）；node web（基线 237 + 新增）；`node --check`；重启 8010 冒烟（Legacy 不变 + modular create 后 telemetry `modular_gnc` 非 null）。

## 不做（Phase 2 另立 ticket）
- environment/load_model 轴（风/一阶浪/mean drift + 波浪资产 + scenario schema）
- 3DOF/roll 栈 curated 真实参数（现合成 scaffold 零阻尼）
- Deployment 工作面 evidence 展示增强

## 执行方式（用户裁决：subagent 实施 + 主 Agent 调配验收）
1. **派发 implement subagent**（加载 `/implement` + `/tdd` 技能，红-绿流程）：prompt 自包含本计划全文 + 文件坐标 + 验证命令；约束：主 checkout 直接实现、只跑聚焦域测试（禁全套——10min 超时丢报告）、禁 colregs-probe、Surgical Changes。
2. **派发 code-review subagent**：对实施 diff 做双轴审查（Standards/Spec），产出问题清单。
3. **主 Agent 独立验收**：逐行 diff 审查 + 修复评审 + 聚焦重跑 + 全套 pytest（预期 1432+新增/9/3）+ node web（237+新增）+ `node --check` + 重启 8010 冒烟（Legacy create 行为不变、modular create 后 telemetry `modular_gnc` 非 null）。
4. 交付报告给用户；commit 由验收后统一处理，push 待用户裁决。