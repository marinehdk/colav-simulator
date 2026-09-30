# M8-A 验收记录 — Quality 双档 + 远景环流送

- 基点：`b03f43dd` → 交付 `effd36fb`（feat(sango): M8-A — quality tiers (high/low) and overlapping-tile streaming）
- 日期：2026-09-29，主 agent 实机验收（workflow dwfrun-8b1fb76f 交付后）

## 交付摘要（workflow 门禁）

- EditMode：基线 308/308 → 门禁 **325/325 全绿**（+17：双档参数契约/swap 合成 fixture（M7 终态泊位/航线/锚地位、out-and-back 恰 2 次翻转、边界抖动不翻转）/迟滞闩锁/分帧队列/装饰随宿主/下拉映射）
- M6+M1 场景重建 exit 0/0；播放器 fresh ✓；M6-Strait.unity 同批回存（diff=恰 +1 "M8 Tile Streaming" GO）
- SampleHeight/Terrain 运行时消费审计：**零消费者**（浮力走 WaterSurface API、锚地=目录水线 y、水深门全在构建期）——swap 无高度场风险
- 构建期校验器 fail-fast：preset 完整性/两档互异/装饰宿主表对 M7BackdropMath 字面量/渔排在宿主矩形/闩锁带宽 sanity

## 实机验收（主 agent CUA + 干净协议）

| 项 | 结果 | 证据 |
|---|---|---|
| High 档基线观感 | ✓ 不回退 | 启动首屏：海峡/船/海面/大气全正常，面板 Quality (M8)=High |
| L 键切 Low + GUI 镜像 | ✓ | `[Sango.M8] hotkey quality -> Low`（Player.log；往返三连 Low→High→Low） |
| Low 档近带辨识度 | ✓ 保持 | Overlook 机位：船体/海面/天际线正常，核心海峡格局不缺失 |
| fps 干净协议 High | ✓ **60.0×6 连读** | `overlays fps (10s avg) = 60.0`（vsync 上限，与 M7 终态同口径） |
| fps 干净协议 Low | ✓ **60.0×5 连读** | 同上；闸门 ≥30（本机 vsync 顶格，低配档余量在低配机兑现） |
| probe 回归 | ✓ **30/30** | `.venv/bin/python tools/sango_zmq_probe.py --count 30` → OK 1.5s（seq 234，20Hz 稳流） |

- 热键账本新增：**L = 画质档循环**（M8-A 提交注释含全仓 KeyCode 核账：0-9/T/F/N/G/V/B/C/A/P/Q/E/Z/X/Space/R/±,./Enter 已占，L 空闲）。
- 视觉差异注记：本机 High/Low 在 Bridge/Overlook 机位观感差异小（降档杠杆=远景 treeDistance 2000→1500/detail 40/pixelError 6/软→硬阴影，主要兑现在低配机与远景树线）；Low 档行为以参数断言+测试背书。

## 流送 swap 实机说明

参考点（hero ship）静止泊位在近带内，交叠 9 tile 维持 inactive（M6 覆盖语义不变）——swap 路径本次未实机触发，以 EditMode 17 项合成 fixture 背书（含迟滞往返/分帧/近带 yield）。**挂账**：M8-B 镜头脚本 G 自航段船出近带 >2km 时由 Player.log `[Sango.M8]` 行顺带取证。

## 遗留

- 双档截图补拍（CUA capture_surfaces_changed 连败，按惯例 pkill 换面）→ 并入 M8-B 完成后 CUA 回归（HUD-off 键实拍）一次做。
- a4000 档验收（全质档+出片）等 license 人闸。
