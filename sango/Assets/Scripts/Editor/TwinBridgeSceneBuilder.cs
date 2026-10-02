using System.IO;
using Unity.RenderStreaming;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sango.Editor.TwinBridge
{
    /// <summary>
    /// P2-S3 Digital Twin 场景/播放器构建器（spec #89）。打开 M6-Strait.unity → 加性注入
    /// "Twin Bridge" GO（SignalingManager + SingleConnection + Broadcast + VideoStreamSender(Camera)
    /// + TwinBridgeChannel + TwinBridgeService + TwinSessionDriver）→ 另存 SangoTwin.unity。
    /// 源场景 M6-Strait.unity 磁盘字节不动。工艺同 UrSpikeSceneBuilder（P2-S2 实证接线），
    /// 差异：spike-echo 换 twin-bridge 正式载体、增 twin 数据面与编排服务、关 AutomaticStreaming
    /// （spike §5.3 遗留：默认设置会在场景加载前对 ws://127.0.0.1:80 建冗余信令连接）。
    /// </summary>
    public static class TwinBridgeSceneBuilder
    {
        const string k_SourceScene = "Assets/Scenes/M6-Strait.unity";
        const string k_TwinScene = "Assets/Scenes/SangoTwin.unity";
        const string k_SignalingUrl = "ws://127.0.0.1:8080";

        [MenuItem("Sango/P2-S3/Build Twin Bridge Scene")]
        public static void BuildTwinScene()
        {
            RenderStreaming.AutomaticStreaming = false; // spike §5.3：关冗余默认信令连接

            var scene = EditorSceneManager.OpenScene(k_SourceScene, OpenSceneMode.Single);

            var camera = Object.FindFirstObjectByType<Camera>(FindObjectsInactive.Exclude);
            if (camera == null || !camera.CompareTag("MainCamera"))
                throw new System.InvalidOperationException("[Sango.TwinBridge] Main Camera not found in M6-Strait");
            var rig = Object.FindFirstObjectByType<Sango.CameraRig>();
            var weather = Object.FindFirstObjectByType<Sango.WeatherController>();
            var session = Object.FindFirstObjectByType<Sango.VisualSimulationSession>();

            var bridge = new GameObject("Twin Bridge");

            var manager = bridge.AddComponent<SignalingManager>();
            var single = bridge.AddComponent<SingleConnection>();
            var broadcast = bridge.AddComponent<Broadcast>();
            var videoSender = bridge.AddComponent<VideoStreamSender>();
            var channel = bridge.AddComponent<TwinBridgeChannel>();
            var service = bridge.AddComponent<TwinBridgeService>();
            var driver = bridge.AddComponent<TwinSessionDriver>();

            // SignalingManager：显式信令 URL（webapp 自托管 :8080）+ handlers 注册（spike 同款接线）。
            // evaluateCommandlineArguments 关闭（P2-S3 实证①）：--sango-twin-bridge 旗标会让 URS 的
            // 命令行解析走 IceServer(urls:null) 分支，_Run 里 op_Explicit(urls.ToArray()) 抛
            // ArgumentNullException，信令进程起不来。iceServers 显式带一条 STUN（P2-S3 实证②）：
            // 序列化为空列表经 SerializeReference 进 player 后不可靠（对端 connect 后不出 offer），
            // 本机回环 ICE 走 host candidates，此条仅为序列化形状兜底（spike 默认资产同款）。
            var so = new SerializedObject(manager);
            so.FindProperty("m_useDefault").boolValue = false;
            so.FindProperty("evaluateCommandlineArguments").boolValue = false;
            so.FindProperty("signalingSettings").managedReferenceValue =
                new WebSocketSignalingSettings(k_SignalingUrl, new[]
                {
                    new IceServer(urls: new[] { "stun:stun.l.google.com:19302" }),
                });
            var handlers = so.FindProperty("handlers");
            handlers.arraySize = 2;
            handlers.GetArrayElementAtIndex(0).objectReferenceValue = broadcast;
            handlers.GetArrayElementAtIndex(1).objectReferenceValue = single;
            so.ApplyModifiedPropertiesWithoutUndo();

            // VideoStreamSender：Camera 捕获主相机，720p30，24bit depth，2-8 Mbps（spike 实证档位）
            var soV = new SerializedObject(videoSender);
            soV.FindProperty("m_Source").enumValueIndex = (int)VideoStreamSource.Camera;
            soV.FindProperty("m_Camera").objectReferenceValue = camera;
            soV.FindProperty("m_TextureSize").vector2IntValue = new Vector2Int(1280, 720);
            soV.FindProperty("m_FrameRate").floatValue = 30f;
            soV.FindProperty("m_Depth").intValue = 24;
            soV.FindProperty("m_AntiAliasing").intValue = 1;
            var bitrate = soV.FindProperty("m_Bitrate");
            bitrate.FindPropertyRelative("min").uintValue = 2000;
            bitrate.FindPropertyRelative("max").uintValue = 8000;
            soV.ApplyModifiedPropertiesWithoutUndo();

            // Broadcast.streams = 视频发送 + twin-bridge 通道（无输入回传：S3 相机经 bridge 命令）
            var soB = new SerializedObject(broadcast);
            var streams = soB.FindProperty("streams");
            streams.arraySize = 2;
            streams.GetArrayElementAtIndex(0).objectReferenceValue = videoSender;
            streams.GetArrayElementAtIndex(1).objectReferenceValue = channel;
            soB.ApplyModifiedPropertiesWithoutUndo();

            // Twin 数据面 + 编排服务引用（运行期 --sango-twin-bridge 自举开闸）
            if (session != null)
            {
                driver.catalog = session.catalog;
                driver.water = session.water;
            }
            if (driver.catalog == null)
            {
                var candidates = Resources.FindObjectsOfTypeAll<VesselCatalog>();
                if (candidates.Length > 0) driver.catalog = candidates[0];
            }
            service.channel = channel;
            service.driver = driver;
            service.cameraRig = rig;
            service.weather = weather;
            service.overlay = Object.FindFirstObjectByType<Sango.DetectionOverlay>()
                ?? bridge.AddComponent<Sango.DetectionOverlay>();

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, k_TwinScene);
            AssetDatabase.SaveAssets();
            Debug.Log($"[Sango.TwinBridge] scene written: {k_TwinScene} (source {k_SourceScene} untouched), signaling={k_SignalingUrl}");
        }

        /// <summary>GUI 运行入口（非 batchmode）：构建（幂等跳过已有）→ 开场景 → 进 Play。</summary>
        public static void PlayTwinScene()
        {
            if (!File.Exists(k_TwinScene))
                BuildTwinScene();
            EditorSceneManager.OpenScene(k_TwinScene, OpenSceneMode.Single);
            EditorApplication.isPlaying = true;
            Debug.Log("[Sango.TwinBridge] play mode requested (executeMethod)");
        }

        /// <summary>macOS 播放器构建（batchmode executeMethod）：仅 SangoTwin 场景，Mono2x，
        /// 输出 Builds/sango-twin.app。macOS 隐私清单（camera/microphone usage description）
        /// 已在 ProjectSettings.asset（P2-S2 spike 落地）。</summary>
        public static void BuildTwinPlayer()
        {
            if (!File.Exists(k_TwinScene))
                throw new System.InvalidOperationException("[Sango.TwinBridge] twin scene missing — run BuildTwinScene first");
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Standalone, "com.colav.sango.twin");
            PlayerSettings.runInBackground = true;
            var report = BuildPipeline.BuildPlayer(
                new[] { k_TwinScene },
                "Builds/sango-twin.app",
                BuildTarget.StandaloneOSX,
                BuildOptions.None);
            Debug.Log($"[Sango.TwinBridge] player build: {report.summary.result} " +
                      $"size={report.summary.totalSize / (1024 * 1024)}MB out={report.summary.outputPath}");
        }
    }
}
