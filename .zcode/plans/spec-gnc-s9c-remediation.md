# 临时 Spec: GNC S9 栈 C — code-review 修复项（Issue #67 合并前）

> 基线: feat/gnc-s9b-acceptance（15 commits）
> 执行分支: feat/gnc-s9c-remediation（自 s9b 分出）
> Worktree: /Users/marine/Code/Colav-Sim-gnc-s9a
> 来源: 双轴 code-review（Standards 3 条 + Spec 轴 2 项缺失）主 Agent 裁决

## 裁决记录（不做项，写进 issue close 注释）

- 返航窗口 planner-state 主路径：descipe。与 ADR-0003 评估器独立于 planner 内部事实的边界冲突；CPA+240s 锚定窗是 planner 无关的保守定义，保留为唯一路径。
- 整定 grid harness：descipe。极点配置种子增益一次通过全部硬门（zigzag/IMO/九宫格），未发生增益整定；未用到的 harness 属 speculative generality。campaign §3 的间距 OFAT 16 候选已完整记录。
- catalog 注册多点散布 smell：记录为未来清理。沿用目录既有 per-identity 结构约定，重构超出本任务外科手术边界。

## 修复项（顺序执行，每项红→绿→commit）

### R1 参数更名 `yaw_limit_base_nm`/`yaw_limit_cap_nm` → `_n_m` 后缀

- 依据：本领域 `nm` 读作海里（CONTEXT.md 语境），实为牛顿·米力矩，Mysterious Name
- 范围：controller.py（dataclass 字段+hash canonical+from/to dict）、catalog.py（preset 注入）、全部引用的测试文件、若有 yaml 引用一并改；`yaw_limit_speed_coeff` 无歧义不改
- 机械更名，语义零变化；全量 grep 确认无残留旧名；相关测试全绿

### R2 calm-straight XTE facade 测试（spec Testing Decisions 承诺缺失）

- 新测试：FCB45 tier1 与 tier2 plant × fcb45_marine_pid，直航线（≥3000m），服务航速 7.8 m/s，静水，走 ModularShipStack facade
- 断言：航线完成；全程 max|XTE| ≤ 10 m（门限=验收门 50m 的 1/5，实现者实测后若 >5m 需回报，不许放宽门限凑数）
- 先例：tests/test_modular_gnc_fcb45_maneuvering_anchors.py 的 settle/run 模式

### R3 FCB45 执行器布局资产（spec Implementation Decisions 承诺缺失）

- 新 layout asset：`fcb45_actuator_layout_v1`（vendor ship_config.yaml 提炼）：主推 3×±135kN（x=−18.094, y=−3/0/+3 m），隧道侧推 2×±20kN（x=+21.906/+23.406 m）；roll 通道拒绝（沿用 allocator 现语义）
- rate limit：若 ResolvedActuatorDynamics 支持每执行器速率则主推 200kN/s、侧推 50kN/s；若仅单一值则用保守的 50kN/s 并在资产注释记录
- catalog 注册为 selectable candidate（进 fcb45 plant 的 allocator 轴候选）；**不改推荐栈**（验收默认 ideal 不变）
- 测试：资产几何/限幅断言 + 与 fcb45 plant 组装的 catalog 组合校验 + 一个小闭环冒烟（tier1+allocator+resolved actuator 走 facade，直线跟踪不劣化）

## 操作纪律

沿用 s9b spec §3：分文件跑 pytest（a3_demo/legacy_g6/ros_adapter 单独）、单次 ≤6 分钟、每项 commit、禁 colregs-probe/GUI/core 改动、ruff clean、legacy_g6 零回归。

## 交付

push `git push marine feat/gnc-s9c-remediation`；回报：三项结果（更名触及文件数、XTE 实测值、布局资产测试结果）、回归摘要、commit SHA。
