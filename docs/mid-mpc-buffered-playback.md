# 单船求解与连续态势显示

2026-09-08，延续 `fd4c9ca6` 后的工作区修复。用户选择真实遥测缓冲，接受约 1–3 秒显示延后，优先保证船位连续。

## 原因

- 求解仍与物理仿真推进同步。求解期间没有新的实际船位；旧画面只在最近两包间插值，插值结束便停住。移走 WebSocket 的锁等待并不能单独解决这种“走—停—走”。
- OT T=450s 的实际输入携带严重违反新约束的热启动种子，原求解需 76 次迭代。单目标 ENC 数值图的长 L-BFGS history / barrier 设置放大了恢复耗时。
- CS 旧运行已在 T≈270s 达到终点，但 Web 层在发布 FINISHED 前同步执行完整评估与文件输出。用户看到最后一包 RUNNING，于是表现为卡死。
- HO 原 WPT2 `[N=6961500, E=43500]` 位于陆地。

## 修改

### 连续显示

`telemetry-playback.js` 放在 Session Runtime 与只读 Telemetry Projection 之间。运行权威与控制命令仍立即处理；显示端积累约 3 秒真实数据，由独立播放时钟持续在已经收到的前后帧之间插值。

地图、显示时间、威胁与规划面板都消费该延后时间轴。离散风险/规划事实保留对应源帧，连续船位只在两帧内插值，不外推，也不使用 MPC 预测冒充实际运动。相同源帧内仅刷新船位与时间，避免每个动画周期重建图表。

页脚显示 `显示延后 …s`。暂停、重置、会话替换立即清空缓冲；FINISHED 正常排空最后几秒后呈现。数据空档超过缓冲容量时显示 `缓冲中`、保留最后真实船位，不伪造前进。延迟上限测试保留少量调度量化余量。

### 结束状态与报告

先发布物理执行的 FINISHED，再由独立结果 worker 生成评估与文件。`result_ready` 明确区分执行结束和报告就绪；前端在报告就绪后加载结果。旧结果任务不能覆盖新会话。

实测 CS：先正常发布 FINISHED，约 **31.7s** 后报告就绪。此期间不会继续假显示 RUNNING，也不持有会话控制锁。

### 单目标数值策略

带 ENC 的单目标问题改用 adaptive barrier 和较短 L-BFGS history。保留多目标已验证策略、全部硬约束、零 slack、真实 IPOPT 及独立 L4 验收；未放宽安全距离、替换算法或加入 fallback。

冻结 OT 热启动问题：约 **2277ms / 76 iterations → 139ms / 8 iterations**。冻结 HO 慢样本：约 **929ms / 39 iterations → 96ms / 5 iterations**。这些是冻结求解测量，不是整条规划链的耗时保证；首次建图仍有开销。

### HO 航点

保持起点、45° 航向及目标船初始会遇几何，将 WPT2 改为 `[N=6960900, E=42900]`。航线约 **5657m → 4808m**，终点距加载的 ENC 危险几何约 **207m**，全航段和船体余量检查通过。新建 HO 场景加载新航点；既有历史 Run Specification 保留原配置。未修改 600s 场景时限。

## 验证

- 前端完整测试：**258 passed**。包括 2.8s 人工数据空档、暂停/会话替换、终点排空、超过缓冲容量时不外推、相同源序号内本船持续动画。
- 实际浏览器：统一播放时钟下，连续 **180 次目标标记采样全部发生位移**，显示延后约 **2.7s**；最长采样间隔 95ms。该采样证明观察窗口内没有周期性标记停住，并非所有机器的帧率保证。本船同序号内绘制另有实际 renderer 回归。
- OT / HO / CS 产品配置：**3 passed，165.54s**。Mid-MPC + God + FCB45 plant / pass-through guidance / FCB45 PID，ideal / calm，seed 0，CPA safe/hard 200/180m，80×5s，10s 求解周期。
- 三者均无会话失败、碰撞或搁浅，无 fallback；每帧检查实际 ENC 船体间距。
- OT / HO 按原 600s 场景时限结束，**没有声称到达航点**；CS 约 268.5s 到达目标。
- 最小中心距 OT / HO / CS：约 **510.9 / 228.5 / 260.1m**。
- 完整规划链在该次产品测试中，排除首帧后的最大耗时约 **1163 / 1038 / 484ms**。优化没有使全部求解低于 200ms；连续显示依赖真实帧缓冲，而非隐藏或改写耗时数据。
- Web transport / 结果线程检查：**19 passed**；真实 API/离线身份/终态专项：**3 passed**。
- L4、性能、parity、Web 专项批次：**59 passed**；冻结数值性能组新增单船热启动夹具后 **6 passed**。
- Ruff check 与 `git diff --check` 通过。全库/历史单船质量套件不在本轮通过声明内。

证据位于 `tmp/debug_mid_motion/`：`product_final.log`、`product_final/*/metrics.json`、`browser_motion_samples.json`、`live_probe.json`、`frontend_verified.log`、`api_finalization.log`、`web_clock.log`、`warm_base.log`、`warm_adaptive.log`、`ho_adaptive.log`。

本轮修复与 OT 岸外航点调整一起提交、推送；8010 重启后使用新建 OT 会话加载新航点。

## OT 航点补齐

OT 的 WPT2 同样改为 `[N=6960900, E=42900]`，与 HO 一致；保留 OT 原起点及目标船设置，航线约 6364m 缩至 5515m。产品回归同时检查 OT/HO 全航段与岸外终点的 ENC 余量。
