# P3 残留清零批 — 台账项裁决记录（spec #89 收尾，2026-10-02）

双轴 review（`7c7b1f3e..720c8239`）F5/F7–F12 中按"入档裁决、不再改代码"处理的两项。
本批其余项（channelOpen 调试标志、探针翻页、F5 缩排、F7/F8/F9/F10）见 commit 与
`sango/Docs/contracts/twin-bridge-v1.md` §8 演进记录。

## F11 — bundle id `com.colav.sango.workbench → com.colav.sango.twin` 变更

**裁决：构建标识有意变更，无运行时影响。已评审接受，不再改。**

事实链：

- `7c7b1f3e`（场景 workbench 期）引入 `Standalone: com.colav.sango.workbench`。
- `a430fc62`（P2-S3）建独立 twin 播放器 `sango/Builds/sango-twin.app` 时改为
  `Standalone: com.colav.sango.twin`（`ProjectSettings.asset` applicationIdentifier 与
  构建产物 `Contents/Info.plist` CFBundleIdentifier 一致），此后 S4/修复批/P3 批未再动。
- 代码侧零读取：仓库内无任何脚本/桥代码分支于 bundle id；影响面仅 macOS 应用身份
  （LaunchServices/安装覆盖语义）。Player.log 路径按 company/product 名派生而非 bundle id，
  product 名未变；探针日志候选路径（`DefaultCompany/sango[-twin]/Player.log`）在 twin id
  下实测命中（S3/S4/修复批双探针全 PASS 即运行时无影响的经验证据）。

## F12 — 诊断计数器非原子 / 非 volatile（容忍陈旧）

**裁决：纯诊断面，容忍陈旧读数。已评审接受，不再改。**

事实：`TwinSessionDriver` 计数器面 —— `m_RxCount`（long，WS 收包线程
`Interlocked.Increment` 写 / `Interlocked.Read` 读，跨线程安全）；
`m_MalformedCount`（WS 收包线程 `++`，主线程经 `Status`/属性读，plain int 无 volatile）；
`m_AcceptedCount`/`m_DuplicateCount`/`m_RebuildCount`/`m_UnslottedCount`（主线程独占写读）。

接受理由：

- 计数器只服务 HUD 状态行与日志/探针诊断（`Status` 字符串、probe-console），**不参与任何
  闸门、重连或控制流判定**——读数陈旧一帧无行为后果，单调计数语义也不因漏计一次读数破坏。
- word 对齐 int 的读写在该平台无撕裂；缺 barrier 只意味着可见性延迟（下次读取即追上），
  为非功能路径加 `volatile`/`Interlocked` 属于无收益的同步开销与噪音 diff。
- F10 新增的 `TwinBridgeService.MalformedClockCount` 同口径：DataChannel 回调主线程独占写，
  plain int，只作诊断/探针读数（写路径单线程，无跨线程写写竞争）。
