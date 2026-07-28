# Workspace Hand-off Log

## [2026-07-24 16:40] Agent: Antigravity (IDE)
- **Git Commit**: `a385e0f` (branch: `main`)
- **任务目标 (Goal)**: 本地完整部署并测试 Colav-Simulator Ecosystem 4个算法库 (psbmpc, rrt-rs, rlmpc, vimmjipda)，实现与 Simulator 集成，并构建统一 Web GUI 控制台验证自定义 MPC 避碰航线规划算法。
- **核心改动 (Actions)**:
  - `/Users/marine/Code/ecosystem/`: 本地拉取并构建了 `psbmpc`, `rrt-rs`, `rlmpc`, `vimmjipda` 源码仓库与 C++/Rust 绑定。
  - `colav_simulator/guidance/custom_mpc_adapter.py`: 创建 `CustomMPCAdapter` 与 `CustomMPCBase` 适配器，使得自定义 MPC 算法可以直接注入到 Colav-Simulator 仿真循环中。
  - `gui_server/main.py`: 基于 FastAPI/WebSocket 开发 Web GUI 仿真服务端，支持场景与算法动态切换。
  - `web_gui/`: 实现现代暗黑极客风 Web GUI 交互界面（Canvas 电子海图、预测时域、COLREGs 风险指标监控与实时控制）。
  - `tests/test_ecosystem_integration.py`: 编写生态系统全套 4 个库的集成验证测试。
- **当前状态 (Status)**: GREEN (所有单元测试及集成测试通过：`17 passed, 2 skipped`；Web GUI 服务运行于 `http://127.0.0.1:8000`)
- **接力指示 (Hand-off Context)**:
  - 虚拟环境位于 `.venv/`，运行 `source .venv/bin/activate` 即可直接加载所有生态库。
  - 启动 Web GUI 控制台：`python -m uvicorn gui_server.main:app --host 127.0.0.1 --port 8000`。
  - 用户可随时在 `colav_simulator/guidance/custom_mpc_adapter.py` 中继承 `CustomMPCBase` 注入自研 MPC 算法。

## [2026-07-24 18:08] Agent: Antigravity (IDE)
- **Git Commit**: `655fefe` (branch: main)
- **任务目标 (Goal)**: Step1 接入真实算法 psbmpc/rrt-rs/rlmpc；Step2 实现 ENC 电子海图可视化
- **核心改动 (Actions)**:
  - `colav_simulator/guidance/custom_mpc_adapter.py`: 全部重写，新增 PSBMPCWrapper/RRTStarGuidance/AcadosMPCWrapper + ALGORITHM_REGISTRY
  - `gui_server/main.py`: ENC subprocess 渲染 + `/api/enc_tile` `/api/enc_info` `/api/algo_status` + 算法注册表 + matplotlib Agg 顶层
  - `web_gui/app.js`: 完整重写 — ENC 底图加载/UTM坐标系/Canvas叠加/algo status pills
  - `web_gui/index.html`: ENC 状态徽章/图层开关/算法状态行
  - `web_gui/style.css`: ENC badge/toggle/algo-pill 样式
- **当前状态 (Status)**: ✅ GREEN — 服务器运行在 http://127.0.0.1:8000
  - ENC PNG 生成成功（Rogaland_utm33.gdb，UTM33，origin 39000/6956450）
  - PSBMPC 真实 C++ 库 ready（TrackedObstacle 9元素格式已修复）
  - RRT-Star 真实 Rust 库 ready（LOS 跟踪模式，ENC 三角剖分待接入）
  - RLMPC fallback 到 SimpleLinearMPC（需要安装 torch）
- **接力指示 (Hand-off Context)**:
  - 下一步优先：浏览器验证 ENC 底图 UTM→canvas 坐标映射是否对齐
  - PSBMPC 需要传入真实 grounding_hazards（Shapely 多边形）才能有非零 chi_opt
  - RRT* 完整规划需要 ENC 三角剖分（transfer_enc_hazards + transfer_safe_sea_triangulation）
  - 激活 RLMPC：pip install torch 后重启服务器

## [2026-07-24 18:17] Agent: Antigravity (IDE)
- **Git Commit**: `7011210` (branch: main)
- **任务目标 (Goal)**: 修复 Web GUI 界面未展示海图（ENC 呈现空白/无内容）的问题
- **核心改动 (Actions)**:
  - `config/seacharts.yaml`: 在 `files` 列表补充包含 `"More_og_Romsdal_utm33.gdb"`（解决坐标 origin [39000, 6956450] 超出 Rogaland 数据范围导致几何体为空的问题）
  - `gui_server/main.py`: 在 subprocess 渲染脚本中加入到 `seacharts/data/external` 的自动符号链接
  - `web_gui/_enc_tile.png`: 重新生成 42.7KB 完整海图 PNG（包含 180+ 陆地、海岸线、0~100m 水深多边形）
- **当前状态 (Status)**: ✅ GREEN — http://127.0.0.1:8000
  - `/api/enc_info` 返回 `ready: true`, origin_e: 39000, origin_n: 6956450
  - `/api/enc_tile` 正常输出 42.7KB PNG 海图瓦片，前端 Canvas 自动对齐并叠加显示
- **接力指示 (Hand-off Context)**: 海图未展示问题已彻底解决，界面图层开关 `🗺 Toggle` 可平滑控制 ENC 背景显示。

## [2026-07-28] ZCode / bb15a17..22b045d (3 commits) / design-grounding Step3-6 完成（动态 MPC 避碰 Playground）

### Task Goal
完成 Dynamic MPC Playground 的 `/design-grounding` Step3 深度调研（第七批 BL-65..69 起）至 Step6 方案包交付。该 Playground 作为核心 MPC 避碰算法的正确性/有效性/公平对比验证平台。

### Core Changes (worktree `/Users/marine/Code/.worktrees/Colav-Simulator/colav-backend-algorithms`, branch `codex/colav-backend-algorithms`)
- **Step3 (commit bb15a17, +1856 行)**: BL-01..118 全部盲区闭环（117 闭环 + 1 边界已确认）；证据矩阵 R1..R79（79 条 DOMAIN_EVIDENCE/PROJECT_FACT/DOCUMENTED_INTENT，三类置信度分列）。第七~十五批，含 COLREG 行为 Oracle (BL-70..74, Woerner/Eriksen verbatim)、统计方法 (BL-85..89, Wilson/KM/bootstrap)、PSB/RLMPC 归一化 (BL-109..113, primary source code verbatim)。
- **Step4 (commit 4ae4344, +357 行)**: DP-05..31 共 27 项推荐综合；VR-05..31 登记；TD-01..04 无 DECOMPOSITION_INCOMPLETE。
- **Step5+6 (commit 22b045d, +731 行)**: 7 项关键 DP 经 DESIGN-IT-TWICE（DP-08/19/21/22/24/25/30 全采纳方案 A）；DP-30 PSB sway `v` 冲突解决（`v:=0, method="native_assumption_course_aligned"`）；ALT-05..18 登记；术语表(17 术语)+技术规约表(六类)+方案包八组件。
- **新增文件**: `docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md`（196 行，独立方案包）。
- **配置**: `.nlm/` 复制自 MASS-L3-Tactical Layer（6 领域笔记本，本会话 token 过期未用，供后续）。

### Current Status
- ✅ design-grounding 全 6 步完成；方案包已交付 brainstorming（未调用，等用户在新对话启动）。
- ✅ Worktree 干净；3 checkpoint 链完整可追溯。
- 🟡 NLM 笔记本 token 过期（需交互 `notebooklm login` 重新认证）；A 档 BL-75..89 三批全走 primary source，证据完整但未用笔记本 sharpen。
- 🟡 未修改主工作区（本对话只做设计调研，不写实现代码）。

### Investigation Chain
- **源身份修正 5 处**（已在 R 条目标注）：R51=C²A(非 Connectivity-Based Culling)、R56=MSC.232(82) ECDIS(原标 MSC.192(79) 错)、R58=MSC.192(79) 实为雷达标准、R59=Namgung 单作者 Route Planning(原标 et al.)、R2=115991 经 Crossref API 权威确认正确(子 agent 误报 115861，已纠正)。
- **PSB/RLMPC native layout 取证**：读 ecosystem 源码 verbatim，发现 PSB native `[x,y,chi,U]`(4D) 有真实 plant_prediction；RLMPC Viknes `[x,y,chi,U,V,r]`(6D) r=psi_dot native 存在。
- **2 个 latent bug**：KinematicShip 构造参数误绑(dt_predictor→LOS_LD)；AcadosMPCWrapper 调不存在的 solve() 永远 fallback。
- **核心方法论发现**：COLREGS 条约仅 1 角度(22.5° abaft beam)，其余全 versioned；crash=MNAR 非 MCAR；物理碰撞须同步时间 CCD 非中心距。

### Pitfalls & Gotchas
- **子 agent 编号冲突**：多 agent 并行时各自用 R 编号会冲突（BL-75..79 agent 用 R69..72，与 BL-80..84 已占用的 R69..72 撞）。须主会话统一分配编号。
- **子 agent 源身份误报**：BL-75..79 agent 误报 Hagen 文章号 115991→115861，经 Crossref API 纠正。须主会话交叉验证子 agent 的事实修正。
- **Edit 字符串匹配**：盲区注册表多行替换因中间夹其他行（如 BL-109..113）导致整块不连续匹配失败，须分段替换。
- **NLM token**：subagent 无法交互登录，`setup --auth` 假阳性（只查 token 文件不查有效性）。
- **grep "未调研" 误匹配**：正文引用含"未调研"词，须用 python 精确解析注册表状态列。
- **rtk grep 多文件输出混乱**：用 `--color=never` + 单文件 + 行号锚点更可靠。

### Handoff Notes (for next session)
- 方案包契约明确：brainstorming 不得推翻 VR-01..31 / 重提 ALT-01..18 / 改技术规约，除非新矛盾证据回炉 design-grounding。
- 实现期须修复 15+ 代码缺陷（详见方案包组件 8）。
- 诚实边界 EXTERNAL_CONFIRMATION_REQUIRED 不阻塞 V1：FCB45 目标 plant / CATZOC 数值表 / metocean / Agder / 历史许可。
- UNKNOWN 项不阻塞设计：容差数值 / route_exit 阈值 / canonical t·seed 数 / HCI / maritime auto-promotion / PSB INFEASIBLE。

### Next Steps (新对话核心提示词)

```
Continue from branch `codex/colav-backend-algorithms` at HEAD `22b045d`
(worktree: /Users/marine/Code/.worktrees/Colav-Simulator/colav-backend-algorithms).
本对话只做设计调研/方案，不写实现代码、不修改主工作区。

仓库与边界：
- 主仓：/Users/marine/Code/Colav-Simulator（main，clean，head 239aa22，本对话不碰）
- 独立 worktree：/Users/marine/Code/.worktrees/Colav-Simulator/colav-backend-algorithms
- 分支：codex/colav-backend-algorithms
- 当前 HEAD：22b045d（design-grounding Step5+6 完成）
- 本会话 commit 链：bb15a17(Step3) → 4ae4344(Step4) → 22b045d(Step5+6)
- ecosystem 源码（只读取证）：/Users/marine/Code/ecosystem/{psbmpc,rlmpc,rrt-rs,vimmjipda}

已完成（design-grounding 全 6 步）:
- ✅ Step1-2（前序会话）：决策点 DP-01..31 + 技术分解 TD-01..04 + grilling
- ✅ Step3：BL-01..118 全部盲区闭环（117 闭环 + BL-02 边界已确认）；证据矩阵 R1..R79
- ✅ Step4：DP-05..31 共 27 项推荐综合；VR-05..31 登记
- ✅ Step5：7 项关键 DP 经 DESIGN-IT-TWICE（DP-08/19/21/22/24/25/30 全采纳方案 A）；
  DP-30 PSB sway `v` 冲突解决（v:=0, method="native_assumption_course_aligned"）；
  ALT-05..18 登记
- ✅ Step6：术语表(17) + 技术规约表(六类) + 方案包八组件（独立文件）

核心产出（必读）:
- docs/superpowers/design-logs/2026-07-27-dynamic-mpc-playground-design-log.md（3344 行，Step1-6 完整溯源）
- docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md（196 行，八组件方案包，brainstorming 权威输入）

未完成 / 待继续（新对话任务）:
- [ ] 调用 superpowers:brainstorming，方案包作为权威输入注入，开始工程细节设计
- [ ] brainstorming 产出 Spec（必须包含方案包的技术规约表和术语表，不得修改已裁决内容）
- [ ] brainstorming → writing-plans → executing-plans（实现期修复 15+ 代码缺陷）
- [ ] 可选：notebooklm login 重新认证后，用 /nlm-ask 查领域笔记本 sharpen A 档证据

方案包契约（brainstorming 权限边界，不可违反）:
- ✓ 可做：工程细节设计（架构/组件/数据流/错误处理/测试），已裁决方案内优化拔高
- ✗ 不可做：推翻 VR-01..31（除非发现新矛盾证据→回炉 design-grounding）
- ✗ 不可做：重提 ALT-01..18（已弃用方案）
- ✗ 不可做：修改技术规约（单位/坐标系/符号），需改则回 design-grounding

排查链路总结（核心方法论发现）:
1. COLREGS 条约仅 1 角度（22.5° abaft beam，Rule 21 灯光弧），其余阈值全 versioned engineering choice；
   三 A-grade source 给三个不同 head-on 半角（Woerner 13°/Eriksen 22.5°/Murray 5°）→ oracle 必须 profile-parameterized
2. 物理碰撞/搁浅 = truth footprint + 同步时间 CCD（C²A conservative advancement）；
   禁止中心距/CPA 冒充物理碰撞，禁止两船独立 swept union 后相交（须同步时间 A(t)∩B(t)）
3. 三类 buffer 必须分离：numerical tolerance（grid_size<<beam）/ chart uncertainty（CATZOC 标签非数值 buffer）/ safety buffer（COLREG 安全域）
4. crash/timeout = MNAR（Missing Not At Random，由算法不稳定性驱动）非 MCAR；
   绝不丢弃（complete-case "generally inappropriate"）/绝不插补 episode_max（偏向不稳定算法）
5. 统计方法：failure-rate→Wilson（非 Wald）；censored arrival→Kaplan-Meier；
   paired continuous→paired-t/Wilcoxon/bootstrap；CRN 仅外生输入（不同步 visibility）

源身份修正（已入日志，勿再误报）:
- R2 Hagen 2023 = Ocean Engineering 288:115991（Crossref 权威确认正确，子 agent 曾误报 115861）
- R51 = C²A 论文（非 "Connectivity-Based Culling"）
- R56 = MSC.232(82) ECDIS（原 brief 标 MSC.192(79) 错）；R58 = MSC.192(79) 雷达标准
- R59 = Namgung 单作者 "Local Route Planning..."（非 et al. "Ship Domain-Based..."）

已知 latent bug（实现期修复，不阻塞设计）:
1. KinematicShip 构造参数误绑：dt_predictor=15.0→LOS_LD, dt_sim=0.5→LOS_K_i（custom_mpc_adapter.py:191-194, psbmpc.py:67-75）
2. AcadosMPCWrapper 调不存在的 TrajectoryTrackingMPC.solve() + 读不存在的 "x_pred"（custom_mpc_adapter.py:481-491）→ 永远 fallback

下一步建议:
1. 读方案包 docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md（八组件）
2. 读设计日志 docs/superpowers/design-logs/2026-07-27-dynamic-mpc-playground-design-log.md（完整溯源，重点 Step4 VR + Step5 决策卡片）
3. 调用 superpowers:brainstorming，声明方案包契约（不得推翻已裁决/重提弃用/改规约）
4. brainstorming 产出 Spec → writing-plans → executing-plans

关键文件:
- docs/superpowers/specs/2026-07-27-dynamic-mpc-playground-solution-pack.md（方案包，brainstorming 输入）
- docs/superpowers/design-logs/2026-07-27-dynamic-mpc-playground-design-log.md（设计日志，3344 行）
- colav_simulator/core/colav/colav_interface.py（ICOLAV 接口，VR-08 薄 Adapter 基础）
- colav_simulator/core/colav/diagnostics.py（PlanStatus/PlannerTrace，VR-13/14 基础）
- colav_simulator/experiment/contracts.py（RunSpec/Manifest/SeedBundle，VR-19/24 基础）
- colav_simulator/simulator.py（collision/grounding oracle 缺陷，VR-21 修复目标）
- colav_simulator/evaluation/{evaluator,encounter}.py（COLREG oracle 重建，VR-22 目标）
- colav_simulator/common/{map_functions,vessel_data,math_functions,miscellaneous_helper_methods}.py（footprint/CPA 缺陷）
- colav_simulator/guidance/custom_mpc_adapter.py（legacy，ALT-04 弃用 + 2 latent bug）
- colav_simulator/integrations/psbmpc.py（正式 PSBMPCColav，VR-30 映射基础）
```
