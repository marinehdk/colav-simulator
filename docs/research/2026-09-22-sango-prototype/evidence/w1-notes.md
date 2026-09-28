# W1（逼真性启动批）验收笔记 — 2026-09-28

编排：主 agent + 两个 dynamic workflow（Run-α Flash 子代理 / Run-β 默认子代理）+ 主 agent CUA 段。
范围：`af24b8c5..56b02724`（5340f3e1 docs / 77411b99 卫生批 / a49d059c+25a9911b symlink 对冲净零 / 56b02724 spike）。

## 验收矩阵

| 项 | 判据 | 结果 | 证据 |
|---|---|---|---|
| A1 三份文档 | 落盘+提交+事实无编造 | ✅ | 主 agent 独立读文复核（登记表逐 dll 5 条、清单 ±$20 口径差如实标注） |
| A2 雾距修复 | EditMode 全绿 + 雾距真实生效 | ✅ | 133/133（含 WeatherFogOverrideTests）；F 键 3000→1000m 实拍：岛清晰轻霭→下半吞没中等雾化（w1-fog-3000/1000.jpg） |
| A2 census fogEn ovr=True | （原判据） | **改判** | `.Override()` 落在 `volume.profile` 运行时实例（WeatherController.cs:161-170），census 读 `sharedProfile` 资产天然看不见——仪表口径局限非缺陷；验收以 F 键视觉差异为准 |
| A2 uGUI 合并 | 行为零变化 | ✅ | 编译+全量绿；细节归 code-review |
| B2 spike 视觉 | 艏波可见 | ✅ | 航行中（~5m/s）追尾近距：V 形波脊从艏张开+两侧扩散波纹+艉部白沫拖带（m4-spike-bowwave-sailing.jpg/.2.jpg）；停船后 decal 自动关（速度门限设计行为——首轮采样误判源于此） |
| B2 spike fps | Mac ≥30 | **❌→M4 项** | 干净测量 25.0–28.4（overlays fps 10s 均值，Player.log）；deformation+foam 512/512 表面级成本（与 decal 开关无关）。M4 处置方向：deformationRes 256 档/Mac 低档门控关变形（对齐"Mac 只载低档"硬件分工） |
| probe 回归 | 30/30 exit 0 | ✅ | `sango_zmq_probe.py --count 30`，30 帧全收 1.0s（seq 415–444，~30Hz 稳定） |
| B1 四画面录屏 | PLAN §1.3 四画面 | ✅ | w1-shot1..4-60s.mp4（内容逐条验过：轨迹/时间球/比例尺、岛数 5→8 面板一致、夜航灯+光路、B0→B8+矢量） |
| EditMode | ≥124 全绿 | ✅ | 133/133（124 基线 +1 雾 +8 速度门限） |
| symlink 越界 | 无残留 | ✅ | a49d059c 引入→25a9911b 回滚，净零；β 门禁路径改工程相对（tmp/x→sango/tmp/x） |

## 账本修正

- **C 键相机循环实测**：追尾→俯视→船艏→桥楼（与 handoff 记载顺序不同）。
- M2E app 内二进制名 = `sango`（pkill 模式须带 Builds/ 路径区分）。
- Unity CLI：`-testResults` 相对工程目录、`-logFile` 相对 cwd（A2 实证并写入 commit message）。
- census（CameraRig 卷审计）只反映 sharedProfile 资产态；运行时 `volume.profile` 实例的 override 不可见——审计雾/运行时参数时换 `vol.profile` 口径（M4 顺手项）。
- CUA getScreenshot 帧率 ≈0.2–1fps（settle 等待+系统负载敏感），录屏为证据级 timelapse 非平滑视频。

## 挂账 M4

1. spike fps 25–28 <30（见上表处置方向；spike notes §5 档位表）。
2. 尾迹图升级 V 形→湍流（spike notes §7.2）、强度曲线 Froude/波高联动、参数进 Simulation 面板、编目驱动多船接线（§7 全清单）。
3. census 口径扩展（vol.profile）。
