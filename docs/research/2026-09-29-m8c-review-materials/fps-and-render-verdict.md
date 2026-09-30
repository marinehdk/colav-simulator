# M8-C — 双机 fps 记录 + a4000 出片机验收

## fps 干净协议(独立会话+零交互+预热后读稳态,`overlays fps` 10s avg 连读)

| 场景 | Mac(1600×900 windowed) | a4000 | gate ≥30 | 备注 |
|---|---|---|---|---|
| 出生点静置 High 档(HazyClear) | **60.0×6 连读**(20260930 M8-A 验收) | 见下方出片机裁决 | ✓ | vsync 上限,frame_ms 16.67 |
| 出生点静置 Low 档 | **60.0×5 连读**(同上,L 键切换) | — | ✓ | 闸门 ≥30,本机 vsync 顶格 |
| G 自航巡航 / 三档 / 雷暴 / 夜航(Mac) | 未单独采样(M7 时代夜 141/昼 162 旧口径在档) | — | — | 旧行记录于 M2-D/M7 验收,口径不同不混表 |

- **a4000 出片机裁决(20260930)**:a4000 不构建 Linux 实时播放器、不跑实时 fps 门禁——其定位是**离线出片机**,验收口径=**产物帧率精确性**:九段 Constant 60 采样共 10809 帧(5×901+3601+3×901)**逐段 100% 精确无丢帧**,即 60fps 门禁的出片机等价形式。实时 fps 门禁(≥30)由 Mac 侧承担并已达成。
- 判读惯例(vsync 满帧间隔非饱和、water queries/frame=0)沿用 M7 记录。

## a4000 出片链最终形态(20260930 实证)

- 命令:`DISPLAY=:0 XAUTHORITY=<gdm-auth> M8_OUT=tmp/m8-frames Unity -batchmode -force-vulkan -projectPath … -executeMethod Sango.Editor.M8RecordingRunner.RunFromCli`
- **两个决定性修正**(教训入账):
  1. **`-force-vulkan` 必须显式**:缺省 fallback OpenGLCore,HDRP 拒绝渲染(log 明示 "not supported with HDRP")→九段全黑帧(所有帧同 33267 字节=纯色特征);Xvfb/xrdp-X/NVIDIA-X 三个 display 上行为一致,与 X server 无关。
  2. **X server 用 GDM 的 :0**(docker 组只读取 gdm Xauthority 后普通用户可连),Xvfb(无 GPU DRI)与 xrdp X 均不可用于 HDRP。
- 出片吞吐:九段 10809 帧 1080p60 JPEG95 约 8 分钟(RTX A4000 单卡)。
