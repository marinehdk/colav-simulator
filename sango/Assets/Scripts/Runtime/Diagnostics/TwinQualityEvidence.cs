using System;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Experimental.Rendering;
using Unity.RenderStreaming;

namespace Sango.Diagnostics
{
    /// <summary>Opt-in benchmark only: pre-encoder pixels and frame intervals, no Session mutations.</summary>
    public sealed class TwinQualityEvidence : MonoBehaviour
    {
        string m_Output;
        VideoStreamSender m_Sender;
        float m_Next;
        int m_Index, m_Frames;
        double m_Seconds;
        readonly float[] m_Intervals = new float[600];
        readonly FrameTiming[] m_Timing = new FrameTiming[1];
        bool m_Pending;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, "--sango-quality-output");
            string output = i >= 0 && i + 1 < args.Length ? args[i + 1] : Environment.GetEnvironmentVariable("SANGO_TWIN_QUALITY_OUTPUT");
            if (string.IsNullOrEmpty(output)) return;
            var host = new GameObject("DT quality evidence").AddComponent<TwinQualityEvidence>();
            host.m_Output = output; Directory.CreateDirectory(host.m_Output);
            host.m_Next = Time.unscaledTime + 10;
        }

        void Update()
        {
            FrameTimingManager.CaptureFrameTimings();
            m_Intervals[m_Frames % m_Intervals.Length] = Time.unscaledDeltaTime;
            m_Frames++; m_Seconds += Time.unscaledDeltaTime;
            if (m_Sender == null) m_Sender = FindFirstObjectByType<VideoStreamSender>();
            var camera = m_Sender != null ? m_Sender.sourceCamera : null;
            var target = camera != null ? camera.targetTexture : null;
            if (target == null || m_Pending || Time.unscaledTime < m_Next) return;
            m_Next = Time.unscaledTime + 10;
            m_Pending = true;
            int width = target.width, height = target.height;
            var quality = new TwinStreamQualityView { source = Describe(m_Sender), frames = m_Frames,
                seconds = m_Seconds, fps = m_Seconds > 0 ? m_Frames / m_Seconds : 0,
                position = camera.transform.position, rotation = camera.transform.eulerAngles };
            var samples = new float[Math.Min(m_Frames, m_Intervals.Length)];
            Array.Copy(m_Intervals, samples, samples.Length); Array.Sort(samples);
            quality.frame_p95_ms = samples.Length > 0 ? samples[(int)((samples.Length - 1) * 0.95)] * 1000 : 0;
            uint count = FrameTimingManager.GetLatestTimings(1, m_Timing);
            quality.gpu_timing_available = count > 0 && m_Timing[0].gpuFrameTime > 0;
            quality.gpu_ms = quality.gpu_timing_available ? m_Timing[0].gpuFrameTime : 0;
            string name = "frame-" + (++m_Index).ToString("D3");
            AsyncGPUReadback.Request(target, 0, TextureFormat.RGBA32, request => {
                m_Pending = false;
                if (request.hasError) return;
                var png = ImageConversion.EncodeNativeArrayToPNG(request.GetData<byte>(), GraphicsFormat.R8G8B8A8_UNorm, (uint)width, (uint)height);
                File.WriteAllBytes(Path.Combine(m_Output, name + ".png"), png.ToArray()); png.Dispose();
                File.WriteAllText(Path.Combine(m_Output, name + ".json"), JsonUtility.ToJson(quality, true));
            });
        }

        static TwinBridgeVideoState Describe(VideoStreamSender sender)
        {
            var camera = sender.sourceCamera;
            var hd = camera.GetComponent<UnityEngine.Rendering.HighDefinition.HDAdditionalCameraData>();
            return new TwinBridgeVideoState { render_width = camera.targetTexture.width, render_height = camera.targetTexture.height,
                capture_width = (int)sender.width, capture_height = (int)sender.height,
                graphics_api = SystemInfo.graphicsDeviceType.ToString(), gpu = SystemInfo.graphicsDeviceName,
                codec = sender.codec?.mimeType, encoder = TwinStreamQuality.EncoderName(sender.codec),
                antialiasing = hd.antialiasing.ToString(), dynamic_resolution = hd.allowDynamicResolution,
                render_scale = DynamicResolutionHandler.instance.GetCurrentScale(), taa_sharpen = hd.taaSharpenStrength };
        }

        [Serializable] class TwinStreamQualityView
        {
            public TwinBridgeVideoState source;
            public int frames;
            public double seconds, fps, gpu_ms;
            public float frame_p95_ms;
            public bool gpu_timing_available;
            public Vector3 position, rotation;
        }
    }
}
