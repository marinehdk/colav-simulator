# 实现基线证据

- 基线提交：`7011210de9a24cd092c469c80302b8117ee1b2d3`
- 基线分支：`main`，相对 `origin/main` ahead 2
- 隔离实现分支：`codex/colav-paper-closed-loop`
- 原工作区未改动项：`handoff/workspace_log.md`
- 已复制到隔离 worktree 的未跟踪输入：`Design/`、`data/ais_datasets/`、`paper/`、`tools/`、Web GUI 文件
- 原工作区历史测试证据：22 passed、2 skipped
- 新 worktree 首次测试：17 passed、4 failed、3 skipped；失败均为未安装外部生态模块，不能作为算法可用证据
- 当前回归结果：32 passed、1 expected skip；唯一 skip 为缺少遗留 `simdata.pkl` 的显式兼容测试
- 静态检查：目标 Python 模块 `ruff check` 通过；`web_gui/app.js` 通过 `node --check`
- Web 闭环检查：桌面 1440x900、移动端 390x844；无水平溢出、浏览器错误或空 Canvas
- 单步检查：连续两次单步后 `step=2`、`sim_time=0.1 s`；真实 Ålesund ENC 和船舶状态可见

基线后所有正式运行必须记录代码 SHA、dirty 状态、依赖身份、场景/episode 哈希、requested/executed algorithm 和 fallback。
