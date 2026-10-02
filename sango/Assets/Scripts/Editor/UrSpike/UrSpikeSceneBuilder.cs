using System.IO;
using System.Linq;
using Sango.UrSpike;
using Unity.RenderStreaming;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.PackageManager;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sango.Editor.UrSpike
{
    /// <summary>
    /// P2-S2 嵌入决策门 spike 场景构建器（spec #89）。打开 M6-Strait.unity → 加性注入
    /// "URS Spike" GO（SignalingManager + SingleConnection + Broadcast + VideoStreamSender
    /// (Camera 捕获) + InputReceiver + UrsDataChannelEcho + UrsSpikeRuntime）→ 主相机子级挂
    /// TMPro 墙钟覆盖层 → 另存 SangoURSSpike.unity。源场景 M6-Strait.unity 磁盘字节不动。
    /// </summary>
    public static class UrSpikeSceneBuilder
    {
        const string k_SourceScene = "Assets/Scenes/M6-Strait.unity";
        const string k_SpikeScene = "Assets/Scenes/SangoURSSpike.unity";
        const string k_SignalingUrl = "ws://127.0.0.1:8080";

        [MenuItem("Sango/P2-S2/Build URS Spike Scene")]
        public static void BuildSpikeScene()
        {
            var scene = EditorSceneManager.OpenScene(k_SourceScene, OpenSceneMode.Single);

            var camera = Object.FindFirstObjectByType<Camera>(FindObjectsInactive.Exclude);
            if (camera == null || !camera.CompareTag("MainCamera"))
                throw new System.InvalidOperationException("[URS-SPIKE] Main Camera not found in M6-Strait");
            var rig = Object.FindFirstObjectByType<Sango.CameraRig>();
            var weather = Object.FindFirstObjectByType<Sango.WeatherController>();

            var spike = new GameObject("URS Spike");

            var manager = spike.AddComponent<SignalingManager>();
            var single = spike.AddComponent<SingleConnection>();
            var broadcast = spike.AddComponent<Broadcast>();
            var videoSender = spike.AddComponent<VideoStreamSender>();
            var inputReceiver = spike.AddComponent<InputReceiver>();
            var echo = spike.AddComponent<UrsDataChannelEcho>();
            var runtime = spike.AddComponent<UrsSpikeRuntime>();

            // SignalingManager：显式信令 URL（webapp 自托管 :8080）+ handlers 注册
            var so = new SerializedObject(manager);
            so.FindProperty("m_useDefault").boolValue = false;
            so.FindProperty("signalingSettings").managedReferenceValue =
                new WebSocketSignalingSettings(k_SignalingUrl);
            var handlers = so.FindProperty("handlers");
            handlers.arraySize = 2;
            handlers.GetArrayElementAtIndex(0).objectReferenceValue = broadcast;
            handlers.GetArrayElementAtIndex(1).objectReferenceValue = single;
            so.ApplyModifiedPropertiesWithoutUndo();

            // VideoStreamSender：Camera 捕获主相机，720p30，24bit depth，2-8 Mbps
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

            // Broadcast.streams = 发送 + 通道组件（URS 模板同款接线）
            var soB = new SerializedObject(broadcast);
            var streams = soB.FindProperty("streams");
            streams.arraySize = 3;
            streams.GetArrayElementAtIndex(0).objectReferenceValue = videoSender;
            streams.GetArrayElementAtIndex(1).objectReferenceValue = inputReceiver;
            streams.GetArrayElementAtIndex(2).objectReferenceValue = echo;
            soB.ApplyModifiedPropertiesWithoutUndo();

            runtime.signalingUrl = k_SignalingUrl;
            runtime.manager = manager;
            runtime.echo = echo;
            runtime.videoSender = videoSender;
            runtime.cameraRig = rig;
            runtime.weather = weather;
            runtime.clockOverlay = BuildClockOverlay(camera.transform);

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, k_SpikeScene);
            AssetDatabase.SaveAssets();
            Debug.Log($"[URS-SPIKE] scene written: {k_SpikeScene} (source {k_SourceScene} untouched), signaling={k_SignalingUrl}");
        }

        static TMPro.TextMeshPro BuildClockOverlay(Transform camera)
        {
            var go = new GameObject("URS Clock Overlay", typeof(TMPro.TextMeshPro));
            go.transform.SetParent(camera, false);
            go.transform.localPosition = new Vector3(0f, 0.35f, 6f);
            go.transform.localScale = Vector3.one * 0.05f;
            var tmp = go.GetComponent<TMPro.TextMeshPro>();
            tmp.text = "00:00:00.000";
            tmp.fontSize = 40;
            tmp.color = Color.white;
            tmp.alignment = TMPro.TextAlignmentOptions.Center;
            tmp.raycastTarget = false;
#if UNITY_6000_0_OR_NEWER
            tmp.textWrappingMode = TMPro.TextWrappingModes.NoWrap;
#else
            tmp.enableWordWrapping = false;
#endif
            return tmp;
        }

        /// <summary>GUI 运行入口（非 batchmode，Game/HDRP 渲染可用）：构建（幂等跳过已有）→ 开场景 → 进 Play。</summary>
        public static void PlaySpikeScene()
        {
            if (!File.Exists(k_SpikeScene))
                BuildSpikeScene();
            EditorSceneManager.OpenScene(k_SpikeScene, OpenSceneMode.Single);
            EditorApplication.isPlaying = true;
            Debug.Log("[URS-SPIKE] play mode requested (executeMethod)");
        }

        /// <summary>装包冒烟（batchmode executeMethod）：解析版本 + 图形设备落日志。</summary>
        public static void ReportPackages()
        {
            var names = new[] { "com.unity.renderstreaming", "com.unity.webrtc", "com.unity.inputsystem", "com.unity.render-pipelines.high-definition" };
            var all = UnityEditor.PackageManager.PackageInfo.GetAllRegisteredPackages();
            foreach (var name in names)
            {
                var p = all.FirstOrDefault(x => x.name == name);
                Debug.Log($"[URS-SPIKE] package {name} = {(p != null ? p.version : "MISSING")}");
            }
            Debug.Log($"[URS-SPIKE] unity={Application.unityVersion} gfx={SystemInfo.graphicsDeviceType} embedded={Directory.Exists("Packages/com.unity.renderstreaming")}");
        }

        /// <summary>macOS 播放器构建（spike 门重拉证据用；batchmode executeMethod）：
        /// 仅 SangoURSSpike 场景，Mono2x，输出 Builds/sango-urs-spike.app。</summary>
        public static void BuildSpikePlayer()
        {
            if (!File.Exists(k_SpikeScene))
                throw new System.InvalidOperationException("[URS-SPIKE] spike scene missing — run BuildSpikeScene first");
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Standalone, "com.colav.sango.ursspike");
            PlayerSettings.runInBackground = true;
            // URS 的 VideoStreamSender 引用 WebCamTexture → macOS player 构建强制要求相机用途声明。
            // Unity 6000.3 无 PlayerSettings.cameraUsageDescription C# API（CS0117），该值存于
            // ProjectSettings.asset（cameraUsageDescription 键），由仓库直接置值（见本次 diff）。首次
            // 构建失败原文："WebCamTexture class is used but Camera Usage Description is empty in Player Settings."
            var report = BuildPipeline.BuildPlayer(
                new[] { k_SpikeScene },
                "Builds/sango-urs-spike.app",
                BuildTarget.StandaloneOSX,
                BuildOptions.None);
            Debug.Log($"[URS-SPIKE] player build: {report.summary.result} " +
                      $"size={report.summary.totalSize / (1024 * 1024)}MB out={report.summary.outputPath}");
        }
    }
}
