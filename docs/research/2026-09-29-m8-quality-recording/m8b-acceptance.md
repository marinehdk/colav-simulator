# M8-B 验收记录 — Recorder 出片管线 + HUD-off

- 基点:`effd36fb`(M8-A)→ 交付 `dd41aaab`(feat(sango): M8-B — recorder pipeline, shot list, HUD-off toggle)
- 日期:2026-09-29,主 agent 实机验收(workflow dwfrun-4a70df6e 交付后)

## 交付摘要(workflow 门禁)

- com.unity.recorder **5.1.7** 入 manifest+lock(Unity 6 LTS 线)
- **M8ShotList**(纯函数,Sango.Vessels):九段镜头脚本对齐三票制材料清单(5 日间机位+大气三档连续 60s+3 夜航段 h=0);段推进/档位调度/运行参数解析
- **HudVisibility**(Runtime):HUD 集中隐藏/还原(出片路径+H 热键共用同一实现;覆盖 Weather/Simulation 面板等三类 HUD)
- **M8RecordingRunner**(Editor,-executeMethod 契约):batchmode 进 Play Mode→RecorderController(Image Sequence JPEG 95 / 1920×1080 / Constant 60fps / CapFrameRate off / TaggedCamera=MainCamera)→单段参数化(M8_SHOT / M8_SECONDS 环境变量,供 a4000 按段跑)
- EditMode:基线 325/325 → 门禁 **332/332 全绿**(+7:九段完整性/段推进/参数解析/HUD 幂等/录制契约常量)

## 端到端产物核验(主 agent 独立复核)

| 项 | 结果 |
|---|---|
| 验证段 | `docs/research/evidence/m8b-recorder-20260929/m8b-verify-bridge-day.mp4` |
| ffprobe | **H.264 / 1920×1080 / 60fps / 12.02s / 12.2MB** ✓(与录制契约逐项一致) |

- **workflow finding 修正**:workflow 报 "evidence/m8b/ 下无 .mp4" 为 **glob 布局假阴性**——产物核验锚了 `**/evidence/m8b/**`(m8b 子目录),实际产物在 `evidence/m8b-recorder-20260929/`(工程师自选日期后缀目录)。产物本身已随批提交且规格达标。教训再证(M6 先例):**门禁锚数据契约勿锚自创布局**——出片产物路径应进派发规格钉死。
- ffmpeg/ffprobe:/opt/homebrew/bin(转码在工程师段内完成:JPEG 序列→H.264)。

## HUD-off 实机验收(M8-B 新构建播放器)

| 项 | 结果 | 证据 |
|---|---|---|
| H 键隐藏 | ✓ 全画面零面板 | `docs/research/2026-09-29-m8-quality-recording/m8b-overlook-hud-hidden.jpg` |
| H 键还原 | ✓ 面板全恢复 | `m8a-low-bridge.jpg`(还原+Low 档状态) |
| 日志账本 | ✓ | `[Sango.M8] hotkey hud -> hidden (H)`(Player.log) |
| Overlook 遮挡(M7 遗留) | ✓ 解除 | HUD 隐藏态 Overlook 构图无 SIM 面板遮挡,出片路径成立 |

- 补拍截图:`m8b-high-hud-bridge.jpg`(High+HUD)、`m8b-overlook-hud-shown.jpg`(遮挡基线)、`m8b-overlook-hud-hidden.jpg`(隐藏)、`m8a-low-bridge.jpg`(Low+还原)。
- 播放器重建 fresh(exit 0),键位账本新增 **H=HUD 集中隐藏/还原**。

## a4000 终版出片(待 license)

管线就绪,license 落地后按段跑:`M8_SHOT=<shot> M8_SECONDS=60 <unity> -batchmode -projectPath sango -executeMethod <runner> -logFile ...`(研究档 §推荐管线:Xvfb+Vulkan 通路已验证,Image Sequence+ffmpeg 转码)。

## 遗留

- 九段全量 60s 出片=a4000 终版任务(等 license 人闸:RDP/Hub GUI 登录,窗口已在用户屏幕)。
- 三票制评审材料=M8-B 九段出片后按协议档 §4 模板打分。
