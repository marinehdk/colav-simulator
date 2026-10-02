using System;
using System.Collections;
using System.IO;
using Unity.RenderStreaming;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Utilities;

namespace Sango.UrSpike
{
    /// <summary>
    /// P2-S2 嵌入决策门 spike 运行时（spec #89，全加性）：
    /// ①信令参数落地（ws://127.0.0.1:8080，早于 SignalingManager.Awake，execution order -200）；
    /// ②证据日志（流/通道生命周期，墙钟毫秒）；③浏览器 JSON 命令派发（view/time/key/shot/quit）——
    /// twin-bridge-v1 控制面形态实证；④原生输入注入证据（InputSystem onAnyButtonPress）；
    /// ⑤墙钟覆盖层文字更新（TMPro，随主相机入流，供玻璃到玻璃延迟取样）；
    /// ⑥本地直渲染对照截图（相机 RT → PNG）。不改既有场景语义：本地热键/legacy 输入不受影响。
    /// </summary>
    [DefaultExecutionOrder(-200)]
    public class UrsSpikeRuntime : MonoBehaviour
    {
        public string signalingUrl = "ws://127.0.0.1:8080";
        public string outputDir = ""; // 空 = $URS_SPIKE_OUT 或 Assets/../output/sango-urs-spike

        public SignalingManager manager;
        public UrsDataChannelEcho echo;
        public VideoStreamSender videoSender;
        public Sango.CameraRig cameraRig;
        public Sango.WeatherController weather;
        public TMPro.TextMeshPro clockOverlay;

        static readonly long s_BootUnixMs = UrsDataChannelEcho.NowUnixMs();

        [Serializable]
        class SpikeCmd
        {
            public string type;
            public string cmd;
            public string view;
            public string key;
            public float hours = -1f;
            public string name;
            public double sendTs;
        }

        void Awake()
        {
            Application.runInBackground = true; // 失焦不停流（采集/演示口径）
            if (manager == null) manager = GetComponent<SignalingManager>();
            if (echo == null) echo = GetComponent<UrsDataChannelEcho>();
            if (videoSender == null) videoSender = GetComponent<VideoStreamSender>();
            if (cameraRig == null) cameraRig = FindFirstObjectByType<Sango.CameraRig>();
            if (weather == null) weather = FindFirstObjectByType<Sango.WeatherController>();

            if (manager != null && !manager.useDefaultSettings)
                manager.SetSignalingSettings(new WebSocketSignalingSettings(signalingUrl));

            if (echo != null)
            {
                echo.OnStartedChannel += id => Log($"echo channel STARTED conn={id}");
                echo.OnStoppedChannel += id => Log($"echo channel STOPPED conn={id}");
                echo.onJson += HandleJson;
            }
            if (videoSender != null)
            {
                videoSender.OnStartedStream += id => Log($"video stream STARTED conn={id}");
                videoSender.OnStoppedStream += id => Log($"video stream STOPPED conn={id}");
            }

            // 原生输入注入证据：浏览器键 → InputRemoting → InputSystem 注入设备按键
            InputSystem.onAnyButtonPress.Call(control =>
                Log($"native-input button={control.name} device={control.device.name} layout={control.device.layout}"));
            Log($"boot url={signalingUrl} unity={Application.unityVersion} gfx={SystemInfo.graphicsDeviceType} " +
                $"outDir={ResolveOutputDir()}");
        }

        void Update()
        {
            if (clockOverlay != null)
                clockOverlay.text = $"{DateTime.Now:HH:mm:ss.fff}";
        }

        void HandleJson(string json)
        {
            SpikeCmd cmd;
            try
            {
                cmd = JsonUtility.FromJson<SpikeCmd>(json);
            }
            catch (Exception e)
            {
                Log($"json parse fail: {e.Message}");
                return;
            }
            if (cmd?.cmd == null)
                return;
            switch (cmd.cmd)
            {
                case "view":
                    if (cameraRig != null && Enum.TryParse(cmd.view, out Sango.CameraView view))
                    {
                        cameraRig.SetView(view);
                        Log($"cmd view -> {view}");
                    }
                    break;
                case "time":
                    if (weather != null && cmd.hours >= 0f)
                    {
                        weather.timeOfDayHours = Mathf.Clamp(cmd.hours, 0f, 24f);
                        Log($"cmd time -> {weather.timeOfDayHours:F1}h (applyEveryFrame 生效)");
                    }
                    break;
                case "key":
                    Log($"cmd key={cmd.key}");
                    if (cameraRig != null && cmd.key == "C") cameraRig.CycleView();
                    break;
                case "shot":
                    StartCoroutine(SaveLocalRenderPng(string.IsNullOrEmpty(cmd.name) ? "local" : cmd.name));
                    break;
                case "ping":
                    Log($"cmd ping sendTs={cmd.sendTs:F1}");
                    break;
                case "quit":
#if UNITY_EDITOR
                    Log("cmd quit -> exit play mode + editor");
                    UnityEditor.EditorApplication.isPlaying = false;
                    UnityEditor.EditorApplication.delayCall += () => UnityEditor.EditorApplication.Exit(0);
#endif
                    break;
                default:
                    Log($"cmd unknown: {cmd.cmd}");
                    break;
            }
        }

        /// <summary>本地直渲染对照：当前视频源 RT（= 相机渲染输出，编码器输入）落 PNG。</summary>
        IEnumerator SaveLocalRenderPng(string name)
        {
            yield return new UnityEngine.WaitForEndOfFrame();
            var rt = videoSender != null ? RenderTexture.active : null;
            var cam = cameraRig != null ? cameraRig.controlledCamera : null;
            if (cam == null || cam.targetTexture == null)
            {
                Log($"shot {name}: no camera targetTexture");
                yield break;
            }
            var prev = RenderTexture.active;
            RenderTexture.active = cam.targetTexture;
            var tex = new Texture2D(cam.targetTexture.width, cam.targetTexture.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, cam.targetTexture.width, cam.targetTexture.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            string dir = ResolveOutputDir();
            Directory.CreateDirectory(dir);
            string path = Path.Combine(dir, $"local-{name}.png");
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Destroy(tex);
            Log($"shot {name} -> {path}");
        }

        static void Log(string msg) =>
            Debug.Log($"[URS-SPIKE] {msg} (boot+{(UrsDataChannelEcho.NowUnixMs() - s_BootUnixMs)}ms)");

        static string ResolveOutputDir()
        {
            var env = Environment.GetEnvironmentVariable("URS_SPIKE_OUT");
            if (!string.IsNullOrEmpty(env)) return env;
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "output", "sango-urs-spike"));
        }
    }
}
