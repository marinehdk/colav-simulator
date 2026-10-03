# S6 E2E 探针挂起 — 根因报告（spec #90 验收阻塞项）

- date: 2026-10-03
- tool: `tools/sango_phase3_e2e_probe.mjs`（主 Agent 环境 4/4 确定性挂起于 Deployment twin 入口段）
- verdict: **产品 bug**（非探针 bug）— `web_gui/modules/situation-display.js` 的 `drawGrid` 在零尺寸画布 + 被污染视图状态下进入真死循环，渲染主线程被永久阻塞，所有 CDP evaluate 超时。

## 根因链（证据齐全）

1. **图表宿主**：2D 态势图 `#canvasWrapper` 位于 `#liveView`（`data-workface-panel="deployment"`，index.html:265/493）——默认 `hidden`。探针全程停在 Config 工作面 → wrapper `clientWidth/Height` 恒为 **0×0**。
2. **视图污染**（session A）：`beginSession('A')` → `initENC` → ENC 瓦片（7000×7000）加载完成 → `img.onload → fitENCView()` 在 0×0 wrapper 上计算：`viewScale = max(0.005, max(0/7000, 0/7000)) = 0.005`，`panX = -17.5`，`panY = +17.5`。`beginSession` 不重置 viewScale/pan —— 污染值跨会话存活。ENC ready 后 `renderCanvas` 走 `drawENCTile`（0 尺寸下无害），session A 全程健康。
3. **死循环触发**（session B）：会话替换 → `beginSession('B')` 置 `encReady=false`（viewScale/pan 不动，仍是污染值）→ 下一个 WS envelope → `renderCanvas` → `!encReady` → `drawGrid(W=0, H=0)`：
   - `gridWorld = chooseGridSpacing(0/0.005 = 0) = 0`（opts 全 0，find 失败回退 `opts[3]=0`）
   - `gridPx = 0 × 0.005 = 0`；`cx = 0/2 + (-17.5) = -17.5`
   - `x0 = Math.floor(-cx/gridPx) = Math.floor(+∞) = +∞`，`x1 = +∞`
   - `for (let i = +∞; i <= +∞; i++)`：**`i++` 在 ±Infinity 上是无操作 → 真死循环**，主线程 100% CPU 永久阻塞。
4. **探针表现**：挂起后任何 `Runtime.evaluate`（工作面切换 click、T 按钮 waitFor、心跳）30s CDP 超时 → 探针死在 Deployment twin 入口段。B3 的 click 本可治愈（panel 展开 → ResizeObserver → resize → 真实 fitENCView），但它排在已死的主线程后面永远执行不到——这解释了"最小复现（先点 Deployment 再遇 ENC 加载）不触发"。

## 取证过程与证据

- 仪表化探针副本（`tools/sango_phase3_e2e_probe_diag.mjs`，诊断后已删除）：页面心跳 `setInterval` 250ms + CDP 超时日志 + **探针启动即预热第二条 CDP 连接**（`Debugger.enable` + `Profiler.enable/start`，200µs 采样）——冷连接在主线程忙死时连 `Runtime.enable` 都无法握手。
- 挂起时（心跳冻结 8s 内触发取证）通过预热连接 `Debugger.pause`：V8 中断忙循环，抓到同步调用栈：

  ```
  drawGrid @ situation-display.js:1137      ← 行/列循环体内
  renderCanvas @ :1071   ← drawGrid(W, H)
  renderFrame @ :2232 ← deployment-view.render (:97)
  renderProjection @ app.js:2718 ← runtime publish ← telemetry-playback.push/emit
  nextSocket.onmessage @ active-session-runtime.js:322
  ```

- **paused 态 evaluate**（debugger 暂停下 evaluate 可运行）读到 `window.__lastGrid`（临时插桩导出的 drawGrid 入参）：
  `{W: 0, H: 0, viewScale: 0.005, panX: -17.5, panY: +17.5, encW: 7000, encH: 7000, encReady: false, scenario: "head_on"}` —— 与上述数值推导逐位吻合。
- CPU profile（320k 样本）：`drawGrid` 37k 自样本 + canvas 原语（stroke/beginPath/moveTo/lineTo 各 ~8-9k，恰为每网格线一组 beginPath→moveTo→lineTo→stroke）。
- macOS `sample <renderer-pid> 3`：主线程 99.5% CPU 于 V8 JIT 区（旁证）。

## 非确定性解释

触发需要「session A 的 ENC 瓦片在 wrapper 隐藏期间加载完成」（污染）+「session B 的 envelope 在瓦片加载后到达」（进入 grid 路径）。瓦片加载失败/过慢时 pan 保持 0，`floor(-0/0)=NaN` 循环体 0 次执行 → 健康。本机 5 次复现 3 次挂（run3 未挂：瓦片未在窗口内就绪）；主 Agent 环境 4/4、交付 subagent 环境全过 = 各机加载时序差异。**挂起与 Deployment twin/URS video/YOLO/tracks §6 渲染无关**（被怀疑的这些路径全程无辜）。

## 修法（web_gui/modules/situation-display.js，2 处守卫 + 缓存戳）

1. `drawGrid` 入口：`if (!(W > 0 && H > 0) || !(gridPx > 0) || !Number.isFinite(gridPx)) return;` —— 渲染路径对任意退化几何（0 尺寸 wrapper、0/∞/NaN 网格距）变为全函数（total），死循环不可能再构成。
2. `fitENCView`：wrapper 无可用尺寸时跳过 fit —— 不再向 viewScale/pan 写入跨会话存活的退化值（0.005/∓17.5）；真实 fit 由既有的治愈路径承担（wrapper 展开 → ResizeObserver → resize → fitENCView）。
3. 三处 stateful 导入边（app.js / config-shell.js / evaluation-replay.js）的 `situation-display.js?v=` 缓存戳统一 bump 至 `20261003-grid-guard-v1`（仓库惯例）。
4. 回归测试：`tests/web_gui/situation-display.test.mjs` 新增「zero-sized wrapper (hidden workface) never degenerates the grid into infinite loop bounds」——0×0 wrapper 下 ENC 加载 → 视图不被污染（0.45）；会话替换后 grid 路径 renderFrame 必须返回（旧代码此处永不返回）；展开后视图正确 fit。

修复后探针连续两次 39/39 PASS（见 `README.md` / `evidence-status.json`），四回归探针全绿（obs 探针首跑出现一次与本修复无关的 `detections=0` 抖动：mast 相机画面内无目标（远目标仅地平线亮点），YOLO 判 0 属正常；静默重跑 23/23 PASS）。
