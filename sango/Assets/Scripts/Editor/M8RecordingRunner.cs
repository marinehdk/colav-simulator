using System;
using System.Collections;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Recorder;
using UnityEditor.Recorder.Input;
using UnityEngine;

namespace Sango.Editor
{
    /// <summary>
    /// M8-B 出片 Runner（-executeMethod 入口，batchmode 契约式静态方法；Recorder 仅 Play Mode
    /// 可 StartRecording——进 Play Mode 录制，录完自退编辑器，命令行**不带 -quit**）。
    /// 流程：RunFromCli 解析环境变量 → 参数入 SessionState（跨 play-enter 域重载存活）→
    /// isPlaying=true → [InitializeOnLoad] 引导在 **EnteredPlayMode** 时机建录制宿主
    /// （关键：进 Play 若伴随资产域重载，play 前建在场景里的编辑器程序集组件会丢——
    /// "referenced script missing" 实证；宿主在进入后创建则无此问题）→ HUD 强制 off
    /// （HudVisibility.Hide，M8-C 材料条件）→ 画质钉 High → 逐段应用镜头脚本
    /// （CameraRig.SetView / WeatherController 时刻+大气档 / 主船 Toggle 自航）→
    /// 构建 RecorderController（Image Sequence JPEG 1080p60，Constant 60，CapFrameRate off）→
    /// Prepare/Start → 轮询 IsRecording() 收段 → StopRecording → HUD Restore →
    /// ExitPlaymode → EditorApplication.Exit(0)。
    /// 参数（环境变量，供 a4000 按段跑）：M8_SHOT=all|段名|序号（空=all）；M8_SECONDS=段时长
    /// 覆盖（冒烟/验证段）；M8_OUT=帧序列输出根目录（默认 sango/tmp/m8b-frames，每段一子目录）。
    /// 时钟契约：业务驱动只读 Time.time（Constant 60 下 Recorder 自设 captureDeltaTime=1/60，
    /// 渲染与游戏时间解耦；禁读墙钟——DateTime.Now/realtimeSinceStartup 一律不碰，研究档 Q2）。
    /// </summary>
    public static class M8RecordingRunner
    {
        public const string EnvShot = "M8_SHOT";
        public const string EnvSeconds = "M8_SECONDS";
        public const string EnvOut = "M8_OUT";
        public const string DefaultScenePath = "Assets/Scenes/M6-Strait.unity";
        public const string DefaultOutRoot = "tmp/m8b-frames"; // 相对工程根解析（sango/）

        internal const string kSessionPending = "M8B.Pending";
        internal const string kSessionParams = "M8B.Params";

        /// <summary>-executeMethod M8RecordingRunner.RunFromCli</summary>
        public static void RunFromCli()
        {
            var shotSpec = Environment.GetEnvironmentVariable(EnvShot);
            var secondsSpec = Environment.GetEnvironmentVariable(EnvSeconds);
            if (!M8ShotList.TryParseRunParams(shotSpec, secondsSpec, out var p, out var error))
            {
                Debug.LogError($"[Sango.M8B] run params invalid: {error}");
                EditorApplication.Exit(1);
                return;
            }
            var outRoot = Environment.GetEnvironmentVariable(EnvOut);
            if (string.IsNullOrEmpty(outRoot)) outRoot = DefaultOutRoot;

            var scenePath = Environment.GetEnvironmentVariable("M8_SCENE");
            if (string.IsNullOrEmpty(scenePath)) scenePath = DefaultScenePath;
            EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);

            // 参数过 SessionState 桥（play-enter 域重载后仍存活）；宿主由 M8RecordingBoot 在
            // EnteredPlayMode 时机创建（此间无资产刷新域重载，编辑器程序集组件稳定）。
            SessionState.SetString(kSessionParams, $"{(p.AllShots ? 1 : 0)};{p.ShotIndex};{p.SecondsOverride.ToString("R", System.Globalization.CultureInfo.InvariantCulture)};{ResolveProjectRelative(outRoot)}");
            SessionState.SetBool(kSessionPending, true);
            EditorApplication.isPlaying = true; // 官方 CommandLineRecorder 教程模式：-executeMethod 进 Play Mode
        }

        /// <summary>解析 "all;idx;seconds;outRoot"（SessionState 桥格式；分隔符 ';' 路径安全）。</summary>
        internal static bool TryParseSessionParams(string raw, out M8ShotList.RunParams p, out string outRootAbsolute)
        {
            p = default;
            outRootAbsolute = null;
            var parts = raw.Split(';');
            if (parts.Length != 4) return false;
            p.AllShots = parts[0] == "1";
            if (!int.TryParse(parts[1], out p.ShotIndex)) return false;
            if (!float.TryParse(parts[2], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out p.SecondsOverride)) return false;
            outRootAbsolute = parts[3];
            return true;
        }

        /// <summary>
        /// 单段录制配置构建（纯配置；EditMode 测试经反射断言契约：Constant 60 / CapFrameRate off /
        /// JPEG 95 / 1920x1080 / TaggedCamera+MainCamera tag / 时间区间 = [0,duration]）。
        /// outputFile 不含扩展名（FileNameGenerator 自动补 .jpg）。
        /// </summary>
        public static RecorderControllerSettings BuildTakeSettings(string outputFile, float durationSeconds)
        {
            var controllerSettings = ScriptableObject.CreateInstance<RecorderControllerSettings>();
            controllerSettings.FrameRatePlayback = FrameRatePlayback.Constant; // 出片一律 Constant（Variable = 墙钟错位根源）
            controllerSettings.FrameRate = M8ShotList.RecordingFps;
            controllerSettings.CapFrameRate = false;                           // 墙钟限速 = 时间轴错位根源（m8b 研究档 Q2），恒关
            controllerSettings.SetRecordModeToTimeInterval(0f, durationSeconds);

            var cam = new CameraInputSettings(); // 输入设置为普通类（非 ScriptableObject，5.1 API）
            cam.Source = ImageSource.TaggedCamera; // HDRP 下 ActiveCamera 不可靠（Recorder 5.1 known issues）
            cam.CameraTag = M8ShotList.CameraTag;
            cam.OutputWidth = M8ShotList.RecordingWidth;
            cam.OutputHeight = M8ShotList.RecordingHeight;

            var seq = ScriptableObject.CreateInstance<ImageRecorderSettings>();
            seq.Enabled = true;
            seq.OutputFormat = ImageRecorderSettings.ImageRecorderOutputFormat.JPEG; // Image Sequence = 跨机一致格式（Linux 无 MP4 直出）；成片由 ffmpeg 转 H.264
            seq.JpegQuality = M8ShotList.JpegQuality;
            seq.OutputFile = outputFile + DefaultWildcard.Frame; // 帧号 0000 起 4 位零填充
            seq.imageInputSettings = cam; // 5.1 属性名 camelCase（m_ImageInputSelector 消费）

            controllerSettings.AddRecorderSettings(seq);
            return controllerSettings;
        }

        /// <summary>相对工程根的路径 → 绝对路径（batchmode 进程 CWD 不可靠，一律锚工程根）。</summary>
        public static string ResolveProjectRelative(string path)
        {
            if (Path.IsPathRooted(path)) return path;
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", path));
        }
    }

    /// <summary>
    /// play-enter 域重载后重新武装的引导（InitializeOnLoad 每次域加载都跑）：Pending 置位时在
    /// EnteredPlayMode 时机建录制宿主——此刻 play 已完全进入，之后不再有资产域重载。
    /// </summary>
    [InitializeOnLoad]
    static class M8RecordingBoot
    {
        static M8RecordingBoot()
        {
            EditorApplication.playModeStateChanged -= EnteredPlay;
            EditorApplication.playModeStateChanged += EnteredPlay;
        }

        static void EnteredPlay(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredPlayMode) return;
            if (!SessionState.GetBool(M8RecordingRunner.kSessionPending, false)) return;
            SessionState.SetBool(M8RecordingRunner.kSessionPending, false); // 只消费一次

            if (!M8RecordingRunner.TryParseSessionParams(
                    SessionState.GetString(M8RecordingRunner.kSessionParams, ""),
                    out var p, out var outRoot))
            {
                Debug.LogError("[Sango.M8B] session params lost across play-enter reload — abort");
                EditorApplication.Exit(1);
                return;
            }
            var hostGo = new GameObject("M8RecordingHost");
            var host = hostGo.AddComponent<M8RecordingHost>();
            host.Configure(p, outRoot);
            Debug.Log($"[Sango.M8B] host created in play mode (all={p.AllShots} idx={p.ShotIndex} secOvr={p.SecondsOverride:0.##} out={outRoot})");
        }
    }

    /// <summary>录制宿主（编辑器程序集内 MonoBehaviour，仅 Play Mode 存活；EnteredPlayMode 时创建）。</summary>
    class M8RecordingHost : MonoBehaviour
    {
        public bool AllShots;
        public int ShotIndex;
        public float SecondsOverride;
        public string OutRoot;

        CameraRig m_Rig;
        WeatherController m_Weather;
        WaypointFollower m_HeroFollower;
        RecorderController m_Controller;
        int m_TakeIndex = -1;
        float m_TakeStartGameTime;
        M8ShotList.TierSwitch[] m_TierSchedule;
        int m_TierCursor;
        string m_TakeDir;
        bool m_SawRecording; // 本段至少见过一帧录制中（StartRecording 失败即 fail-fast，不静默出空段）
        bool m_TakeEnding;

        public void Configure(M8ShotList.RunParams p, string outRootAbsolute)
        {
            AllShots = p.AllShots;
            ShotIndex = p.ShotIndex;
            SecondsOverride = p.SecondsOverride;
            OutRoot = outRootAbsolute;
        }

        IEnumerator Start()
        {
            // 等场景落定：WeatherGUI 面板构建/首 Apply、tile 流送首帧、浮力起步
            yield return null;
            yield return null;

            HudVisibility.Hide();                  // Recorder 路径强制 HUD off（结束 Restore）
            M8Quality.SetTierFromDropdownIndex(0); // 出片钉 High（M7 终态基线；下拉序 = High/Low）

            m_Rig = FindFirstObjectByType<CameraRig>();
            m_Weather = FindFirstObjectByType<WeatherController>();
            var followers = FindObjectsByType<WaypointFollower>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            foreach (var f in followers)
            {
                if (f.demoHotkeysEnabled) { m_HeroFollower = f; break; } // M6 主船判别：demoHotkeysEnabled 仅主角接线
            }
            if (m_Rig == null || m_Weather == null)
            {
                Debug.LogError("[Sango.M8B] scene missing CameraRig/WeatherController — abort");
                EditorApplication.Exit(1);
                yield break;
            }

            BeginTake();
        }

        void BeginTake()
        {
            m_TakeIndex = AllShots ? m_TakeIndex + 1 : ShotIndex;
            if (m_TakeIndex >= M8ShotList.ThreeVoteNine.Length)
            {
                FinishAll();
                return;
            }
            var shot = M8ShotList.ThreeVoteNine[m_TakeIndex];
            float duration = SecondsOverride > 0f ? SecondsOverride : shot.DurationSeconds;

            // 段状态应用：机位（CameraRig 1s smoothstep 过渡落在段首 3s 静置窗内）/时刻/大气/自航
            m_Rig.SetView(shot.View);
            m_Weather.timeOfDayHours = shot.TimeOfDayHours;
            m_TierSchedule = M8ShotList.TierSchedule(shot);
            m_TierCursor = 0;
            ApplyTier(m_TierSchedule[0].Tier);
            if (shot.StartDemo && m_HeroFollower != null && !m_HeroFollower.DemoRunning)
                m_HeroFollower.Toggle(); // G 键同源启航

            // 录制会话（每段独立 settings/controller，输出各归段名子目录）
            m_TakeDir = Path.Combine(OutRoot, shot.Name);
            Directory.CreateDirectory(m_TakeDir);
            var settings = M8RecordingRunner.BuildTakeSettings(Path.Combine(m_TakeDir, shot.Name + "_"), duration);
            m_Controller = new RecorderController(settings);
            m_Controller.PrepareRecording();
            m_Controller.StartRecording();
            m_TakeStartGameTime = Time.time; // 此后 Time.time 以 1/60 步进（captureDeltaTime 由 Recorder 自设）
            m_SawRecording = false;
            m_TakeEnding = false;
            Debug.Log($"[Sango.M8B] take start: {shot.Name} dur={duration:0.##}s fps={M8ShotList.RecordingFps} out={m_TakeDir}");
        }

        void ApplyTier(M7BMath.AtmosphereTier tier)
        {
            m_Weather.atmosphereTier = tier;
            m_Weather.ApplyAtmosphereTier(); // 从当前值起 smoothstep 过渡（preset transitionSeconds）
            m_Weather.Apply();
        }

        void Update()
        {
            if (m_TakeIndex < 0 || m_Controller == null || m_TakeEnding) return;

            float t = Time.time - m_TakeStartGameTime;
            while (m_TierCursor < m_TierSchedule.Length && t >= m_TierSchedule[m_TierCursor].AtLocalSeconds)
            {
                if (m_TierCursor > 0) ApplyTier(m_TierSchedule[m_TierCursor].Tier); // 索引 0 已在 BeginTake 应用
                m_TierCursor++;
            }

            if (m_Controller.IsRecording())
            {
                m_SawRecording = true;
                return;
            }
            // 官方模式：TimeInterval 到点会话自结束 → IsRecording()==false 即收段；
            // 未曾见过 IsRecording()==true = StartRecording 失败（如 tag/相机缺失）→ fail-fast
            if (m_SawRecording) EndTake();
            else if (t > 1f)
            {
                Debug.LogError($"[Sango.M8B] StartRecording never began (tag={M8ShotList.CameraTag}?) — abort");
                EditorApplication.Exit(1);
            }
        }

        void EndTake()
        {
            m_TakeEnding = true;
            m_Controller.StopRecording();
            int frames = CountFrames(m_TakeDir);
            Debug.Log($"[Sango.M8B] take end: {M8ShotList.ThreeVoteNine[m_TakeIndex].Name} frames={frames} dir={m_TakeDir}");

            if (AllShots && m_TakeIndex + 1 < M8ShotList.ThreeVoteNine.Length)
                StartCoroutine(NextTakeAfterFlush());
            else
                FinishAll();
        }

        IEnumerator NextTakeAfterFlush()
        {
            // ImageRecorder JPEG 写盘异步（帧路径队列）：让编辑器帧消化完再开下一段
            for (int i = 0; i < 30; i++) yield return null;
            BeginTake();
        }

        void FinishAll()
        {
            HudVisibility.Restore(); // 结束恢复（捕获-还原精确对称）
            StartCoroutine(ExitAfterPlay());
        }

        IEnumerator ExitAfterPlay()
        {
            for (int i = 0; i < 30; i++) yield return null; // 末段 JPEG 队列落盘余量
            EditorApplication.isPlaying = false;
            s_QuitPending = true; // QuitWatchStatic 在退出 Play 后退编辑器（命令行不带 -quit）
        }

        static int CountFrames(string dir)
        {
            if (!Directory.Exists(dir)) return 0;
            return Directory.GetFiles(dir, "*.jpg", SearchOption.TopDirectoryOnly).Length;
        }

        void OnEnable()
        {
            // 静态钩子：play mode 退出会销毁宿主——退编辑器动作挂静态处理器，跨宿主销毁存活；
            // Exit 前自摘（幂等减加防重复订阅）。
            EditorApplication.update -= QuitWatchStatic;
            EditorApplication.update += QuitWatchStatic;
        }

        static void QuitWatchStatic()
        {
            if (!s_QuitPending || EditorApplication.isPlaying) return;
            s_QuitPending = false;
            Debug.Log("[Sango.M8B] play mode exited — closing editor (exit 0)");
            EditorApplication.update -= QuitWatchStatic;
            EditorApplication.Exit(0);
        }

        static bool s_QuitPending;
    }
}
