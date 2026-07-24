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
