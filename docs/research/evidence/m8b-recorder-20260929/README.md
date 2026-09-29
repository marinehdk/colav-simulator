# M8-B 出片管线 — Mac 端到端验证证据

- 日期：2026-09-29 ｜ 批次：M8-B（Recorder 出片管线，基点 effd36fb）
- 录制机：Mac（Apple Silicon，Unity 6000.3.24f1 + HDRP 17.3 + com.unity.recorder 5.1.7，batchmode 进 Play Mode 实录）
- 本目录 = M8-C 评审材料（a4000 终版出片）前的**管线验证段**产物

## 产物

| 文件 | 事实（ffprobe 实测） |
|---|---|
| `m8b-verify-bridge-day.mp4` | H.264 / 1920×1080 / 60 fps（60/1）/ **12.016667 s / 721 帧** / 12,181,016 B |

- 镜头段：`bridge-day`（M8ShotList.ThreeVoteNine[0]，Bridge 机位 / HazyClear / 12h），时长以 `M8_SECONDS=12` 覆盖（验证段契约 12–15s）
- 帧数说明：Recorder `SetRecordModeToTimeInterval(0,12)` 含端点 → 721 帧（0000..0720）@60fps = 12.0167 s，如实报告
- 画面核验（抽帧 bridge-day_0400）：桥楼随船机位（船恒在画面）、HazyClear 正午、PP 岸桥天际线远景、**无任何 HUD 元素**（WeatherGUI/SimulationPanel/Radar/FpsProbe/VectorArrows 全隐）

## 复跑命令（a4000 按段跑同一条命令换环境变量）

```bash
# 单段（帧序列 JPEG 落 sango/tmp/m8b-frames/<段名>/，含 -quit 不带：Runner 自退编辑器）
M8_SHOT=bridge-day M8_SECONDS=12 \
/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity \
  -batchmode -projectPath sango \
  -executeMethod Sango.Editor.M8RecordingRunner.RunFromCli \
  -logFile sango/tmp/m8b-record.log

# 环境变量：M8_SHOT=all|段名|序号（空=all 九段连录）；M8_SECONDS=段时长覆盖；M8_OUT=输出根目录
# 段名与清单：bridge-day bow-day chase-day topdown-day overlook-day bridge-atmo bridge-night chase-night overlook-night

# 转码（Linux 同构：Image Sequence 是跨机一致格式，MP4 由 ffmpeg 出）
ffmpeg -y -framerate 60 -start_number 0 -i sango/tmp/m8b-frames/<段>/<段>_%04d.jpg \
  -c:v libx264 -crf 17 -pix_fmt yuv420p -movflags +faststart <out>.mp4
```

## 本批顺带修复（录像素材硬伤，a4000 前必须）

1. `M4_BowWave.mat` / `M4_WakeFoam.mat`：`m_EnableInstancingVariants` 0→1。
2. `HullWaterlineDecals.MakeDecalMaterial`：runtime `new Material(HDRP/Decal)` 补 `enableInstancing = true`。
   根因：HDRP `DecalSystem.RenderIntoDBuffer` **无条件走 `DrawMeshInstanced`**（含单实例，
   DecalSystem.cs:1116）——decal 材质不开 instancing = DBuffer 抛 InvalidOperationException
   → 整帧 RenderGraph 中止 → **录像全黑帧**（1508 次异常/次实录；本批 3 次实录逐次定位）。
