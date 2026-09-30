# M8b 出片管线研究:Unity Recorder 转移 Linux 服务器

- 日期:2026-09-29
- 目标工程:`sango/`(Unity **6000.3.24f1**,changeset `4e7b9b5b6244`,HDRP **17.3.0**,见 `sango/ProjectSettings/ProjectVersion.txt` 与 `sango/Packages/manifest.json`;manifest 目前尚无 `com.unity.recorder`)
- 目标服务器:Ubuntu 22.04,2× RTX A4000 16GB,NVIDIA 驱动 535.309.01,Xorg+GDM 在 tty1 活跃(SSH 下 `DISPLAY` 未设),`xvfb-run` 已装,磁盘剩 124 GB
- 产物需求:60s×N 镜头(五机位各段 + 大气三档切换段 + 夜航段),真帧率视频(非 timelapse)

---

## 结论:推荐管线(一段话)

在 Linux 服务器上**不打包 Player、直接用编辑器 batchmode 出片**:Unity 6000.3.24f1 Linux 编辑器 + `com.unity.recorder` **5.1.7**(Unity 6 LTS 兼容线,见下),挂在**已有的真 Xorg :0 会话**上(SSH 导出 `DISPLAY=:0` + GDM 会话的 `XAUTHORITY`),驱动走 NVIDIA 专有驱动 + **Vulkan**(HDRP 17.3 在 Linux 只支持 Vulkan),**禁用 `-nographics`**;用 `-executeMethod` 进编辑器,按官方 "Launch recordings from the command line" 教程的模式加载体内的 Recorder Settings/Preset 或代码构造 `RecorderControllerSettings` → `EditorApplication.isPlaying = true` 进 Play Mode → `RecorderController.PrepareRecording()/StartRecording()`,轮询 `IsRecording()` 完成后 `StopRecording()` + 退出。**录制速率与播放速率解耦的确切做法 = `Playback=Constant` + Target FPS 60**:Recorder 内部自动设 `Time.captureDeltaTime = 1/60`(源码可证),每渲染帧恰好推进 1/60 s 游戏时间,渲染慢只是录得久、成片时长与节奏不变。**产物:Linux 内置编码器不支持 MP4(H.264)/ProRes**,所以两条路——(a) MovieRecorder 直出 VP8 WebM(快、有损、省盘);(b) **推荐:Image Sequence(JPEG/PNG)+ 服务器 ffmpeg 转 H.264 MP4**,或用包内 FFmpeg custom-encoder sample 在录制时直接管道给 ffmpeg。许可:Unity 6 起 **Personal 不能再走 alf→ulf 手动激活**(官方仅限 Enterprise/Industry 席位或 legacy Pro serial),Personal 官方只认 Unity Hub 登录;实操按 GameCI 惯例在任一有 GUI 的机器 Hub 激活 Personal 后把 `Unity_lic.ulf` 拷到服务器,或试用 2026 年新出的实验性 unity CLI 的 `auth`/`license` 子命令;若可买 Pro 则全程 `-serial` CLI 无痛点。磁盘:Linux 编辑器压缩包实测 4.16 GiB(解压约 9–11 GB)+ 工程 Library 约 3 GB(本仓库实测),124 GB 足够,但 PNG 序列帧必须按镜头"录完即编码即删"。

---

## 逐问题展开

### Q1. Recorder 在编辑器 batchmode 下的脚本化录制(无 Recorder 窗口)

**Recorder 版本(Unity 6 LTS 兼容线)**:Unity Package Registry(packages.unity.com)显示 `com.unity.recorder` 稳定版 5.1.7 的 `unity` 字段为 **6000.0**,且 5.1.7 changelog 明言 "Raised the minimum supported Unity version to **6000.0**";5.1.0–5.1.6 标注 `2023.1`(兼容 Unity 6,因为 Unity 6 内核即 2023.3 改名);4.0.3 是 2022 LTS 线,官方文档也停留在 @4.0。**给 6000.3.24f1 装 5.1.7**(当前最新,2026-07-25 发布)。
来源:[packages.unity.com/com.unity.recorder](https://packages.unity.com/com.unity.recorder)、[needle-mirror/com.unity.recorder package.json](https://github.com/needle-mirror/com.unity.recorder)(Unity 官方私有仓的公开镜像)、[Recorder 5.1 文档](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/index.html)。

**官方背书的 batchmode 录制方案**:Recorder 5.x 官方手册新增教程 [Launch recordings from the command line](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/CommandLineRecorder.html),完整给出 "Recorder Settings Preset + `-executeMethod` + batch 录制队列" 的做法,要点:

1. 在 Recorder 窗口把配置(如 FHD 1080p Movie recorder)存成 **Preset**(`Assets/xxx.preset`),之后所有变体(五机位/大气档/夜航)各存一个 Preset,命令行传 `-presetPath` 选择——正合本项目"镜头脚本"需求。
2. 场景里挂一个 `MonoBehaviour`(`CommandLineRecorder`),**`OnEnable()` 里 `StartRecording`(进入 Play Mode 时触发)**,`Update()` 里 `if (!m_Controller.IsRecording()) { StopRecording(); EditorApplication.ExitPlaymode(); }`。
3. `-executeMethod` 调静态方法 `ExecuteCommandLine()`:解析 `-startFrame/-endFrame/-presetPath` → `SetRecordingInfo()` 写回成员(序列化以便跨 Play Mode 保留)→ 进 Play Mode。
4. 命令行形态(官方 Linux 示例):
   ```
   /home/<user>/Unity/Hub/Editor/<version>/Editor/Unity -projectPath . \
     -executeMethod CommandLineRecorder.ExecuteCommandLine \
     -startFrame 0 -endFrame 10 -presetPath "Assets/HDMovieRecorderSettings.preset"
   ```
   官方原文命令里未出现 `-batchmode`(教程以可交互环境为例),但其工作流明确面向 "batch recording via a job queue of many command lines";社区(CI)实践证明 batchmode 下 RecorderController 可用(见风险节)。

**API 关键约束**:[RecorderController 文档](https://docs.unity3d.com/Packages/com.unity.recorder@4.0/api/UnityEditor.Recorder.RecorderController.html)(API 面在 4.0→5.1 未变)——`StartRecording()` "**works only in Play mode**… Exception: If not in Playmode";`PrepareRecording()` 负责建立录制上下文;`IsRecording()` 返回是否仍在录;`StopRecording()` 落盘。命名空间 `UnityEditor.Recorder`,程序集 `Unity.Recorder.Editor.dll`——**编辑器专用,Player 里不存在**,所以"编辑器 batchmode 出片"是正路。无需 Recorder 窗口;窗口只是另一入口(Recorder 窗口保存的配置在 `Library/Recorder/recorder.pref`)。

**包内官方示例**(Package Manager → Samples,5.1.7):`MovieRecorder Sample`("This example shows how to set up a movie recording session via script")、`MultipleRecordings`、`RecorderEditor`(菜单项 Start/Stop Recording)、`FFmpegCommandLineEncoder`。来源:[com.unity.recorder package.json samples 段](https://github.com/needle-mirror/com.unity.recorder)。

**最小代码骨架**(按官方教程与 5.1.7 `MovieRecorderExample` 综合改造;本工程放 `sango/Assets/Scripts/Editor/M8Recorder.cs`,与现有 `M*.cs` 管线脚本同构):

```csharp
// Assets/Scripts/Editor/M8Recorder.cs  (editor-only assembly)
using System;
using UnityEditor;
using UnityEditor.Recorder;
using UnityEditor.Recorder.Input;
using UnityEngine;

public static class M8Recorder   // -executeMethod M8Recorder.Record
{
    public static void Record()
    {
        // 1) 加载目标场景(或由参数指定),确认五机位 Tag 就位
        //    EditorSceneManager.OpenScene("Assets/Scenes/M6-Strait.unity");

        // 2) 命令行参数:镜头名/机位/时长/天气档等(官方教程用 Environment.GetCommandLineArgs)
        var args = Cli.Parse();                      // -shot shoreline -camera cam05 -seconds 60 -weather night

        // 3) 创建场景内的录制宿主(进 Play Mode 时 OnEnable 起录)
        var host = new GameObject("M8RecorderHost").AddComponent<M8RecorderHost>();
        host.Configure(args);                        // 序列化参数,跨 Play Mode 保留

        EditorApplication.isPlaying = true;          // 官方教程此行在网页代码块中缺失,按机制补齐
    }
}

public class M8RecorderHost : MonoBehaviour
{
    RecorderController m_Controller;

    public void Configure(ShotArgs args)
    {
        var controllerSettings = ScriptableObject.CreateInstance<RecorderControllerSettings>();

        // ---- 帧率解耦核心:Constant + 60(见 Q2)----
        controllerSettings.FrameRatePlayback = FrameRatePlayback.Constant;
        controllerSettings.FrameRate = 60.0f;
        controllerSettings.SetRecordModeToTimeInterval(0f, args.seconds);   // 或 SetRecordModeToFrameInterval

        // ---- 五机位:HDRP 下必须 TaggedCamera(ActiveCamera 对 SRP 不可用,见 Q1 附注)----
        var img = new CameraInputSettings {
            Source      = ImageSource.TaggedCamera,
            CameraTag   = args.cameraTag,            // CameraViews 五机位各打一个 Tag
            OutputWidth = 1920,
            OutputHeight= 1080,
        };

        // ---- Linux 无 MP4:走 Image Sequence(本例)或 WebM(见 Q4)----
        var seq = ScriptableObject.CreateInstance<ImageRecorderSettings>();
        seq.Enabled = true;
        seq.OutputFormat = ImageRecorderSettings.ImageRecorderOutputFormat.PNG;  // 或 JPEG
        seq.OutputFile = $"{args.outDir}/{args.shot}_{args.cameraTag}_" + DefaultWildcard.Generate(DefaultWildcard.FileName);
        seq.InputImageSettings = img;

        controllerSettings.AddRecorderSettings(seq);
        m_Controller = new RecorderController(controllerSettings);
    }

    void OnEnable()   // 进入 Play Mode 触发
    {
        m_Controller.PrepareRecording();
        m_Controller.StartRecording();
    }

    void Update()
    {
        if (m_Controller != null && !m_Controller.IsRecording())
        {
            m_Controller.StopRecording();
            EditorApplication.ExitPlaymode();        // 整个 batch 进程随后由外层脚本 -quit 收尾
        }
    }
}
```

(骨架按 5.1.7 公开 API:`RecorderControllerSettings.FrameRatePlayback/FrameRate/SetRecordModeToTimeInterval/SetRecordModeToFrameInterval/AddRecorderSettings`、`CameraInputSettings.Source/CameraTag/OutputWidth/OutputHeight`、`ImageRecorderSettings.OutputFormat`——字段名均已对照 [needle-mirror 源码](https://github.com/needle-mirror/com.unity.recorder) 核实;`DefaultWildcard`/`FileNameGenerator` 见 [API 命名空间页](https://docs.unity3d.com/Packages/com.unity.recorder@4.0/api/UnityEditor.Recorder.html)。落地时以 IDE 补全为准。)

**附注(HDRP 特有)**:Recorder 5.1 已知问题——SRP(HDRP/URP)下 **ActiveCamera 不可用**,Movie/Image Recorder 必须用 **TaggedCamera**。来源:[Known issues | Recorder 5.1](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/KnownIssues.html)。`CameraViews.cs`(sango 五机位)需给每台相机加 Tag。

### Q2. "Recorder 假设实时帧率 → 回放错位" 的公认绕法(录制/播放速率解耦)

**关于编号**:任务所指 "Unity #14953" 以 UUM-14953 / 14953 检索 [issuetracker.unity3d.com](https://issuetracker.unity3d.com) 与全 web 均无公开页面(issue tracker 对未公开/内部编号返回 404,搜索 API 无命中)。该编号无法公开定位,但所述症状("渲染跟不上实时时,按墙钟打时间戳导致回放卡顿/时间轴错位")与绕法由以下一手来源完整确立:

**机制(Recorder 源码,官方包镜像)**:Playback=**Constant** 时,`RecordingSession.SessionCreated` 里 Recorder 自己设置
```csharp
var fixedRate = settings.FrameRatePlayback == FrameRatePlayback.Constant ? settings.FrameRate : 0.0f;
...
Time.captureDeltaTime = (float)(m_FrameInterval + m_FramePadTime); // 1/fps (+1e-7 防双帧 padding, REC-1105)
```
并检测"若他处已设冲突的 `Time.captureFramerate` 则报 Error"。来源:[Recorder.cs SessionCreated,needle-mirror/com.unity.recorder](https://github.com/needle-mirror/com.unity.recorder)(`Editor/Sources/Recorder.cs` L116–132)。

**引擎机制**:[Time.captureDeltaTime 官方文档(6000.3)](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Time-captureDeltaTime.html)——"If this property has a non-zero value then **Time.time increases at an interval of captureDeltaTime … regardless of real time and the duration of a frame**. This is useful if you want to capture a movie where you need a constant frame rate…"。即:**渲染耗时与游戏时间彻底解耦**,一渲染帧 = 恒定 1/fps 秒游戏时间;渲染再慢,成片按恒定 fps 打时间戳,回放时长/节奏精确。注意文档同时警告 `captureDeltaTime` 不影响 `Time.unscaledTime`——凡是读墙钟(`realtimeSinceStartup`/`DateTime.Now`)的逻辑在录制中会与成片时间轴错位。

**确切配置(Recorder 侧)**:
- `RecorderControllerSettings.FrameRatePlayback = Constant` + `FrameRate = 60`(脚本侧);Recorder 窗口/Preset 等价物 = Playback: **Constant**,Target FPS: 60。
- **不要开 `CapFrameRate`**(Constant 下的 "Cap FPS"):[RecordingSession.cs L233](https://github.com/needle-mirror/com.unity.recorder) 显示 Variable、或 Constant+CapFrameRate 时,Recorder 会按**墙钟** sleep/busy-loop 把渲染节奏往 1/fps 拽——这正是"试图贴合实时"的路径,无头服务器上没必要(只会更慢)。
- 官方语义:[General recording properties](https://docs.unity3d.com/Packages/com.unity.recorder@4.0/manual/RecorderWindowRecordingProperties.html)——"When **Constant** is selected, Recorder applies the same time interval between each recorded frame **without regard to the time required to render the frame**";"**Variable** … captures frames at the rate at which they are rendered … If rendering time increases during recording, the resulting frames are held longer during playback"——**Variable 就是错位来源,出片一律 Constant**。社区同症状旁证:[Unity Recorder movie output is too fast](https://discussions.unity.com/t/unity-recorder-movie-output-is-too-fast/740221)(解法同样是 Constant)、[Recorder slow down 讨论](https://discussions.unity.com/t/unity-recorder-slow-down)(录制时游戏降速到几 fps 属正常,成片仍为目标帧率)。

**工程侧配套**:
- 物理/导航逻辑统一吃 `Time.deltaTime`(=captureDeltaTime)与 `Time.fixedDeltaTime`;`fixedDeltaTime` 取 1/60 或其整数分之一,保证 60fps 下步进均匀。
- sango 的 GNC/海况推进如使用自有时钟(如累计 `Time.time`),天然兼容;如曾用 `Environment.TickCount`/墙钟,出片前必须切到 `Time.time`。
- Frame Interval 模式 `start>0` 时,官方明确 Recorder 仍会**从头逐帧播放**到起始帧以保证确定性(物理/程序噪声),只是不落盘——镜头脚本若从第 N 帧起录,冷启动时间会变长。来源:[General recording properties](https://docs.unity3d.com/Packages/com.unity.recorder@4.0/manual/RecorderWindowRecordingProperties.html)。

### Q3. Linux 无头 GPU 渲染现状(2025–2026)与推荐路径

**Unity 6000.3 编辑器 Linux 官方要求**([System requirements for Unity 6.3](https://docs.unity3d.com/6000.3/Documentation/Manual/system-requirements.html)):Ubuntu 22.04/24.04;GPU 需 "OpenGL 3.2+ 或 Vulkan-capable, Nvidia and AMD GPUs";显示栈要求 "**Gnome desktop environment running on top of X11 or Wayland windowing system**, Nvidia official proprietary graphics driver";且 Ubuntu 22.04 上 Wayland 仅 AMD 官方支持(NVIDIA 需 24.04 + 550+ 驱动)。→ 本服务器(Xorg + GDM + 535 专有驱动)恰在官方支持矩阵内;SSH 环境 `DISPLAY` 未设只影响新会话变量,**不影响 tty1 上已运行的 X server 接受 X11 客户端**。

**`-batchmode` 不带 `-nographics` 能否 GPU 渲染**:能初始化图形设备,但**必须有一个可连接的 X display**——Unity Linux 编辑器没有官方的"无 X 运行"支持;业界事实标准是 [GameCI docker 镜像](https://github.com/game-ci/docker) 把编辑器包成 `xvfb-run -ae /dev/stdout "$UNITY_PATH/Editor/Unity" -batchmode "$@"`(见其 [editor Dockerfile L64](https://raw.githubusercontent.com/game-ci/docker/main/images/ubuntu/editor/Dockerfile))。`-nographics` 则完全不初始化图形设备(官方:[command line arguments](https://docs.unity3d.com/6000.3/Documentation/Manual/EditorCommandLineArguments.html))——Recorder/相机渲染全部不可用,**出片命令行绝不能带 `-nographics`**(社区踩坑:[Reddit: headless Unity Linux](https://www.reddit.com/r/Unity3D/comments/1liv41c/how_to_render_on_headless_mode_in_unity_linux)、[headless docker + GPU 讨论区](https://pavelguzenfeld.com/posts/headless-unity-docker-simulation))。

**三条候选路径评估**:
1. **真 Xorg :0(GDM 会话)+ NVIDIA + Vulkan —— 推荐**。SSH 中 `export DISPLAY=:0` 与 `XAUTHORITY=/run/user/<uid>/gdm/Xauthority`(GDM 会话典型位置,以 `ps e $(pgrep Xorg)` 确认)即可让编辑器上真 GPU。A4000(Ampere)+ 535.309.01 支持 Vulkan 1.3,HDRP 无障碍。
2. **Xvfb —— 仅作无 GPU 兜底,不推荐出片**。Xvfb 是纯软件 X server(虚拟帧缓冲),无 GLX 硬件加速、NVIDIA Vulkan ICD 不经它工作;Unity 在其下退到 Mesa 软渲染(llvmpipe/lavapipe),HDRP 基本不可用。旁证:[Running Linux player under xvfb with CPU rendering](https://discussions.unity.com/t/running-linux-player-under-xvfb-with-cpu-rendering/883028)。
3. **无头 Vulkan(surfaceless/EGL headless)—— 编辑器不支持**。Unity 6 的 "headless" 是 **Player**(Dedicated Server)概念([desktop headless mode](https://docs.unity3d.com/6000.3/Documentation/Manual/desktop-headless-mode.html)),编辑器图形栈仍以 X11 为前提;Recorder 只在编辑器里存在,故此路不通。
   (变体:若怕打扰桌面会话,可在空闲 tty 上自起一个无显示器的 `Xorg :1` + `nvidia-xconfig --allow-empty-initial-configuration` 当录制专用屏,同属路径 1。)

**HDRP 17.3 在 Linux + Vulkan 的已知问题**:
- 官方平台矩阵([HDRP 17.3 System requirements](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/System-Requirements.html)):Linux 仅 **Vulkan**;"HDRP doesn't support OpenGL … **On Linux, Vulkan might not be installed by default. In that case you need to install it manually to run HDRP**"(`vulkaninfo` 已装 → 检查 `nvidia` ICD 即可)。
- 历史问题需要冒烟验证:旧版 "[Linux] Crash on SIGSEGV when creating 3D HDRP Template"(UUM-57861,Vulkan 相关,[issue 页](https://issuetracker.unity3d.com/issues/linux-crash-on-sigsegv-when-creating-3d-hdrp-template));NVIDIA 论坛有 [550 驱动 + Unity Vulkan 编辑器崩溃线程](https://forums.developer.nvidia.com/t/550-47-unity-editor-on-linux-crashes-when-using-vulkan-graphics-backend-with-nvidia-550-drivers/288990)。→ 535 分支未见于此类报告,但**先跑 5s 冒烟镜头再上批量**。
- GPU 选择:两块 A4000 并行时可用官方 [`-force-device-index`](https://docs.unity3d.com/6000.3/Documentation/Manual/EditorCommandLineArguments.html) 指定 GPU(文档说明索引按驱动/Metal/D3D/Vulkan 枚举顺序)——Linux Vulkan 下实际行为需验证;不验证则双进程默认都可能挤在 GPU0。

### Q4. 录制产物与推荐配置

**MovieRecorder 输出格式(Recorder 5.1)**:[Movie Recorder properties](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/RecorderMovie.html)——H.264 MP4 / VP8 WebM / ProRes QuickTime / GIF,由 "Unity Media Encoder"(`CoreEncoderSettings`)承担。**Linux 限制(官方 Known issues)**:"**The Movie Recorder doesn't support H.264 MP4 and ProRes QuickTime encoding on Linux**"。源码双重确认:[CoreEncoderSettings.cs](https://github.com/needle-mirror/com.unity.recorder) 中 `IsCodecSupportedOnThisPlatform()` 在 `UNITY_EDITOR_LINUX` 下对 MP4 返回 false,构造函数在 Linux 默认 `Codec = WEBM`;枚举只有 `MP4`/`WEBM` 两项(VP8,上限 8K)。ProRes 是 macOS 专属编码器。来源:[Known issues | Recorder 5.1](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/KnownIssues.html)。

**Image Sequence 输出**:PNG / JPEG / EXR(`ImageRecorderSettings.OutputFormat`,[源码枚举](https://github.com/needle-mirror/com.unity.recorder))。EXR 为浮点线性(体积巨大),成片不需要。

**推荐**:
- **主路:Image Sequence(JPEG 或 PNG)+ 服务器 ffmpeg → H.264 MP4**。理由:Linux 内置编码器只剩 VP8 WebM 一条(质量/码率控制弱、VP8 已老);序列帧可断点续录、可单帧质检、可多进程并行编码,`ffmpeg -framerate 60 -i frame_%04d.png -c:v libx264 -crf 17 -pix_fmt yuv420p out.mp4` 一行收尾。Ubuntu 22.04 `apt install ffmpeg` 即得。这正是 Recorder 包官方 FFmpeg sample 的思路——`FFmpegCommandLineEncoder` sample 把 MovieRecorder 输出经命名管道直接喂给外部 ffmpeg("Requires your own FFmpeg executable. Tested with FFmpeg 5.0.1",[samples 页](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/samples.html)/[源码](https://github.com/needle-mirror/com.unity.recorder));想要"录完即 MP4"可挂它,想要可控性就用序列帧+离线 ffmpeg。
- **分辨率/帧率**:1920×1080 @ 60fps Constant(与 Mac 播放器观感一致;VP8/H.264 对 4K60 无必要,HDRP 渲染成本也翻倍)。夜航段建议单独 Preset(曝光/ NavigationLights 常亮),大气三档用 WeatherController 三档各录一段。
- **磁盘预算(实测换算)**:1080p60,60s = 3600 帧。PNG≈2–4 MB/帧 → **单镜头 9–14 GB**;JPEG≈0.3–0.5 MB/帧 → **1.3–1.8 GB**;VP8 WebM 60s≈20–80 MB。若全片按 9 段(5 机位 + 大气 3 档 + 夜航)PNG 直录,峰值 80–120 GB,**逼近 124 GB 上限**→ 序列帧"录一段、编一段、删一段"(每镜头闭环),或全程 JPEG。

### Q5. Unity Personal 在 headless Linux 服务器的许可与激活(2025–2026 现状)

**Unity 6 官方文档的硬约束**(全部为 6000.3 手册原文):
- [License activation methods](https://docs.unity3d.com/6000.3/Documentation/Manual/LicenseActivationMethods.html):"Note: **For Unity Personal, the Unity Hub is the only method for activating and returning licences.**"
- [Manage your license through the command line](https://docs.unity3d.com/6000.3/Documentation/Manual/ManagingYourUnityLicense.html):CLI 激活(`-quit -batchmode -serial SB-… -username … -password …`)"**The following procedures don't apply to Unity Personal.** To activate a license for Unity Personal, log in to the Unity Hub."
- [Manual license activation](https://docs.unity3d.com/6000.3/Documentation/Manual/ManualActivationGuide.html)(alf→ulf 流程仍全量保留:`-batchmode -createManualActivationFile` → [license.unity3d.com/manual](https://license.unity3d.com/manual) 上传 .alf → 下载 .ulf → `-batchmode -manualLicenseFile xxx.ulf`):"Manual activation supports two kinds of licenses: assigned seats on a **Unity Enterprise or Unity Industry** subscription, and **legacy serial-based Unity Pro** licenses. It **doesn't support** Unity Pro assigned seats, **Unity Personal**, or floating license subscriptions."

即:**2018–2021 年代"Personal 也能 alf→ulf"的流程在 Unity 6 已收缩**,这正是 2025–2026 的现状变化;`-manualLicenseFile` 本身仍在(Enterprise/Industry/legacy Pro 用)。

**headless Linux + Personal 的实操选项**:
1. **GameCI 惯例(社区事实标准)**:在有 GUI 的任一机器(可以就是这台 Mac)用 Unity Hub 登录并 "Get a free personal license",取 `Unity_lic.ulf`(Linux 路径 `~/.local/share/unity3d/Unity/Unity_lic.ulf`)拷到服务器同路径;GameCI v4 文档称 "Licenses are not tied to a specific Unity version or platform … activate on any operating system … use it for builds on another platform, like Ubuntu",其 [Activation 文档](https://game.ci/docs/github/activation) 以 `UNITY_LICENSE`(ulf 内容)+ `UNITY_EMAIL` + `UNITY_PASSWORD` 作为 Personal 的标准 CI 配置。**注意**:这是社区惯例而非官方支持路径(官方表述见上),存在校验/失效风险,见风险节。
2. **实验性 unity CLI(2026 新)**:Unity 新推独立 [Unity CLI](https://docs.unity.com/en-us/unity-cli/use-unity-cli)("works in CI pipelines … You can install the Unity CLI on machines that don't run the Unity Hub, such as, headless CI workers";Linux 支持 Ubuntu 22.04+),提供 [`auth`(登录)/`license`(在本机列出、激活、返还许可)](https://docs.unity.com/en-us/unity-cli/unity-cli-reference) 子命令——**是目前官方条线里唯一可能覆盖"headless + Personal"的通道**,但整体标注 experimental,`unity license activate` 对 Personal 的支持细节文档未展开,需实测。
3. **一劳永逸**:Pro 序列号 + `-serial -username -password` 全程 CLI([官方命令](https://docs.unity3d.com/6000.3/Documentation/Manual/ManagingYourUnityLicense.html)),服务器无人值守最稳。

需要 Unity ID 登录吗?——路径 1 的 Hub 激活需要;路径 2 的 `unity auth` 需要;路径 3 需要(账号+序列号绑定)。均需联网首次激活;录制备份 `.ulf` 后运行期仅本地校验。

### Q6. 磁盘预算(含实测)

| 项 | 数值 | 证据 |
|---|---|---|
| Unity 6000.3.24f1 Linux 编辑器安装包 | **4,465,840,984 B ≈ 4.16 GiB**(tar.xz) | `download.unity3d.com/download_unity/4e7b9b5b6244/LinuxEditorInstaller/Unity.tar.xz` HTTP HEAD `Content-Length` 实测(2026-09-29) |
| 编辑器解压后 | 约 **9–11 GB** | unityci/editor:ubuntu-6000.3.24f1-base-3 镜像压缩层合计 4.85 GiB(Docker registry API 实测);tar.xz 常规压缩比 2–2.3× |
| sango 工程 Linux 首次导入 Library | 约 **3 GB**(±1) | 本仓库实测:sango/Library = **2.9 GB**(PackageCache 1.7 GB——Linux 上按新平台重新拉包;Artifacts 348 MB;Burst/Bee/ShaderCache ≈ 520 MB),Assets 177 MB |
| 序列帧(1080p60×60s) | PNG 9–14 GB/镜头;JPEG 1.3–1.8 GB/镜头 | 见 Q4 换算 |
| 成片 MP4(60s 1080p60 crf17) | ≈ 0.2–0.5 GB/镜头 | 常规码率 20–60 Mbps |

**合计:编辑器+工程 ≈ 13–15 GB,录制按镜头滚动清理序列帧后峰值可控制在 30–40 GB,124 GB 剩余空间充足。**

---

## 风险与未知

1. **"Unity #14953" 无法公开定位**:UUM-14953 在 [issuetracker.unity3d.com](https://issuetracker.unity3d.com) 无公开页(404)、搜索无命中,可能为内部编号或已下线。绕法不依赖该页面:Constant playback + `Time.captureDeltaTime` 的机制已由引擎文档 + Recorder 源码双源确证(Q2)。
2. **Personal `.ulf` 拷贝与官方文档冲突**:官方明说 "Personal 只能 Hub 激活",GameCI 惯例是拷 ulf + 账号密码;存在某次许可校验收紧后失效的风险。回退:买 Pro 走 `-serial` CLI,或实测实验性 [unity CLI](https://docs.unity.com/en-us/unity-cli/unity-cli-reference) 的 `auth`/`license`。
3. **HDRP + Vulkan + 535.309.01 组合未经本机实测**:先跑 5s 冒烟(单机位、FHD、10s)确认无 UUM-57861 类崩溃、无 NVIDIA 论坛 550 线程类驱动问题;`vulkaninfo | grep -A3 deviceName` 确认 NVIDIA ICD 生效。
4. **官方 CommandLineRecorder 教程的代码块在渲染页上尾部缺失**(进入 Play Mode 的收尾行未显示在网页源码可见范围内),骨架中 `EditorApplication.isPlaying = true` 按机制补齐;以 IDE 实测为准。
5. **`-executeMethod` 在 batchmode 下进入 Play Mode 属于"编辑器批处理 + Play Mode"组合**,官方教程未写明 `-batchmode` 字样(示例命令未带),GameCI 生态大量 `xvfb-run … -batchmode` 编辑器任务佐证可行性,但**带 GPU 的真 X 会话下 batchmode + Play Mode 录制仍属本管线需首次验证的组合**。
6. **`-force-device-index` 在 Linux Vulkan 下的实际枚举顺序未知**(文档只说"按驱动枚举"),双 A4000 并行前需各跑一个冒烟并核对 GPU 占用(`nvidia-smi`)。
7. **多 MovieRecorder 并发会显著减速**(官方 Known issues:"limit yourself to one Movie recording at a time")→ 五机位**串行**,每镜头一个 recorder;Image Sequence 并受此约束。
8. **GDM 会话运维**:SSH 导出 `DISPLAY=:0` + `XAUTHORITY=/run/user/<uid>/gdm/Xauthority` 依赖会话保持(自动注销/锁屏策略需关闭或排除);更稳的是自建录制专用 `Xorg :1`。
9. **CameraViews/CameraRig 尚无相机 Tag**(HDRP 要求 TaggedCamera),M8 落地第一改动点;`RecorderController` 只认编辑器程序集,录制脚本必须放 `Assets/Scripts/Editor/`。

## 主要来源清单

- Recorder 包与版本:[packages.unity.com/com.unity.recorder](https://packages.unity.com/com.unity.recorder);[needle-mirror/com.unity.recorder](https://github.com/needle-mirror/com.unity.recorder)(官方包镜像:package.json、Recorder.cs、RecordingSession.cs、CoreEncoderSettings.cs、Samples)
- Recorder 官方文档:[5.1 manual index](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/index.html) | [Launch recordings from the command line](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/CommandLineRecorder.html) | [Known issues(5.1)](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/KnownIssues.html) | [Movie Recorder properties](https://docs.unity3d.com/Packages/com.unity.recorder@5.1/manual/RecorderMovie.html) | [General recording properties](https://docs.unity3d.com/Packages/com.unity.recorder@4.0/manual/RecorderWindowRecordingProperties.html) | [RecorderController API](https://docs.unity3d.com/Packages/com.unity.recorder@4.0/api/UnityEditor.Recorder.RecorderController.html)
- 帧率机制:[Time.captureDeltaTime(6000.3)](https://docs.unity3d.com/6000.3/Documentation/ScriptReference/Time-captureDeltaTime.html);[Unity Recorder movie output is too fast](https://discussions.unity.com/t/unity-recorder-movie-output-is-too-fast/740221)
- Linux 平台:[System requirements for Unity 6.3](https://docs.unity3d.com/6000.3/Documentation/Manual/system-requirements.html) | [Editor command line arguments(-nographics/-force-device-index)](https://docs.unity3d.com/6000.3/Documentation/Manual/EditorCommandLineArguments.html) | [HDRP 17.3 System requirements](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/System-Requirements.html) | [UUM-57861(Linux HDRP Vulkan 崩溃史)](https://issuetracker.unity3d.com/issues/linux-crash-on-sigsegv-when-creating-3d-hdrp-template) | [NVIDIA 550 + Unity Vulkan 线程](https://forums.developer.nvidia.com/t/550-47-unity-editor-on-linux-crashes-when-using-vulkan-graphics-backend-with-nvidia-550-drivers/288990) | [GameCI docker(editor Dockerfile 的 xvfb-run 包装)](https://github.com/game-ci/docker) | [xvfb CPU rendering 讨论](https://discussions.unity.com/t/running-linux-player-under-xvfb-with-cpu-rendering/883028)
- 许可:[License activation methods(6000.3)](https://docs.unity3d.com/6000.3/Documentation/Manual/LicenseActivationMethods.html) | [Manage your license through the command line](https://docs.unity3d.com/6000.3/Documentation/Manual/ManagingYourUnityLicense.html) | [Manual license activation(alf→ulf)](https://docs.unity3d.com/6000.3/Documentation/Manual/ManualActivationGuide.html)(含 [macOS/Linux CLI 步骤](https://docs.unity3d.com/6000.3/Documentation/Manual/ManualActivationCmdMac.html)) | [GameCI Activation(Personal ulf 惯例)](https://game.ci/docs/github/activation) | [Unity CLI(experimental,auth/license)](https://docs.unity.com/en-us/unity-cli/use-unity-cli)
- 下载体积:[download.unity3d.com/download_unity/4e7b9b5b6244/LinuxEditorInstaller/Unity.tar.xz](https://download.unity3d.com/download_unity/4e7b9b5b6244/LinuxEditorInstaller/Unity.tar.xz)(Content-Length 实测);[unityci/editor Docker registry](https://hub.docker.com/r/unityci/editor)(层大小实测);本地 `du` 实测 sango/Library
