using Unity.RenderStreaming;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>Local WEB capture profiles; no simulation or replay-clock authority.</summary>
    public sealed class TwinStreamQuality
    {
        readonly VideoStreamSender m_Sender;
        public static readonly string[] Profiles = { "1080p", "1440p" };
        public string Profile { get; private set; }

        public TwinStreamQuality(VideoStreamSender sender, bool renderAtStreamRate = false)
        {
            m_Sender = sender;
#if UNITY_STANDALONE_LINUX
            if (Application.isPlaying && !sender.isPlaying)
            {
                foreach (var codec in VideoStreamSender.GetAvailableCodecs())
                {
                    if (codec.mimeType != "video/H264") continue;
                    sender.SetCodec(codec);
                    Debug.Log($"[Sango.TwinVideo] Linux encoder={codec.mimeType} implementation={codec.codecImplementation}");
                    break;
                }
            }
#endif
            var camera = sender.sourceCamera;
            if (camera != null)
            {
                var hd = camera.GetComponent<HDAdditionalCameraData>() ?? camera.gameObject.AddComponent<HDAdditionalCameraData>();
                // AA(20261014 第四轮):cost30(tri30+60fps 全绿)下用户仍见动态段水面拉扯,
                // Unity 循环/投递/元素层全净——嫌疑收敛到内容级。头号:水面不写运动矢量,
                // TAA 对水像素只能相机运动重投影,相机微动(含 BridgeSway)→水纹理错误重投影
                // =脉动拖影,观感"拉扯"。A/B 回 SMAA(历史 M7 选择)。若 SMAA 下仍拉,
                // 再查水面细节法线混叠。
                hd.antialiasing = HDAdditionalCameraData.AntialiasingMode.SubpixelMorphologicalAntiAliasing;
                // Transparent SSR visibly jumps over animated water even with
                // continuous render/stream clocks. Keep the sky/probe fallback
                // on the DT camera; other cameras retain their own settings.
                hd.customRenderingSettings = true;
                var settings = hd.renderingPathCustomFrameSettings;
                settings.SetEnabled(FrameSettingsField.TransparentSSR, false);
                hd.renderingPathCustomFrameSettings = settings;
                var mask = hd.renderingPathCustomFrameSettingsOverrideMask;
                mask.mask[(uint)FrameSettingsField.TransparentSSR] = true;
                hd.renderingPathCustomFrameSettingsOverrideMask = mask;
            }
            // 水面网格密度(20261014 三轮像素法证定案):Env ON chase 段 Unity 主循环 60→34fps
            // (fps-report 锚定实测,75% 重帧)=内容更新率跌至 ~34Hz 不规则→屏幕 38/60 有效帧
            // =用户"拉扯"根因;锚点吸附/波浪几何全部无罪(静相机照卡实证)。triangleSize 15 是
            // 20261014 误诊期加码(4x 近场三角形,未治愈任何伪影,纯耗预算)——回 30 默认还预算。
            // 仅 twin player 生效。
            var globalVolume = Object.FindFirstObjectByType<Volume>();
            if (globalVolume != null && globalVolume.sharedProfile != null
                && globalVolume.sharedProfile.TryGet<WaterRendering>(out var waterRendering))
            {
                waterRendering.triangleSize.Override(30f);
            }
            if (Application.isPlaying)
            {
                Application.runInBackground = true;
                QualitySettings.vSyncCount = 0;
                // 渲染钟(20261014 终局):主循环 60fps 时 Xvfb(报 0.00Hz)对 Vulkan present
                // 做不规则合并——fb 内容账本实测仅 ~37Hz(18-28ms)前进,屏幕 38-45 有效帧
                // =用户「拉扯」。33ms(30fps)低于合并阈、呈 2:2 均匀;历史 30fps 时代的
                // 拉扯来自当时重构建(tri15 等)chase 段掉频+已修 bug 叠加。锁 30。
                Application.targetFrameRate = 30;
            }
            TryApply("1080p");
        }

        public bool TryApply(string profile)
        {
            if (!TrySize(profile, out var size)) return false;
            if (Profile == profile) return true;
            m_Sender.SetTextureSize(size);
            // 30 fps capture measured the smooth ceiling: the sender's capture
            // pass renders the whole HDRP scene a second time (~34 ms/frame at
            // 1080p, ~40 ms at 1440p), so a 60 fps clock only starved the
            // stream (27-29 fps at 1080p, ~25 at 1440p with visible stutter)
            // while the 30 fps clock delivers a rock-steady 29.8.
            m_Sender.SetFrameRate(30f);
            m_Sender.SetBitrate(profile == "1440p" ? 12000u : 8000u, profile == "1440p" ? 30000u : 16000u);
            Profile = profile;
            Debug.Log($"[Sango.TwinVideo] profile={profile} capture={size.x}x{size.y} target_fps=30 bitrate_kbps={m_Sender.minBitrate}-{m_Sender.maxBitrate} aa=SMAA batch={Application.isBatchMode} gpu={SystemInfo.graphicsDeviceType}");
            return true;
        }

        public TwinBridgeVideoState Describe()
        {
            var camera = m_Sender.sourceCamera;
            var hd = camera != null ? camera.GetComponent<HDAdditionalCameraData>() : null;
            var target = camera != null ? camera.targetTexture : null;
            return new TwinBridgeVideoState {
                render_width = target != null ? target.width : camera != null ? camera.pixelWidth : 0,
                render_height = target != null ? target.height : camera != null ? camera.pixelHeight : 0,
                capture_width = (int)m_Sender.width, capture_height = (int)m_Sender.height,
                profile = Profile, graphics_api = SystemInfo.graphicsDeviceType.ToString(), gpu = SystemInfo.graphicsDeviceName,
                antialiasing = hd != null ? hd.antialiasing.ToString() : "Unknown",
                dynamic_resolution = hd != null && hd.allowDynamicResolution,
                render_scale = UnityEngine.Rendering.DynamicResolutionHandler.instance.GetCurrentScale(),
                taa_sharpen = hd != null ? hd.taaSharpenStrength : 0,
                codec = m_Sender.codec?.mimeType, encoder = EncoderName(m_Sender.codec),
            };
        }

        public static string EncoderName(VideoCodecInfo codec)
        {
            // Serialized default VP8 entries can have no implementation parameters.
            // The package's codecImplementation getter dereferences those missing data.
            if (string.IsNullOrEmpty(codec?.sdpFmtpLine)) return null;
            foreach (string part in codec.sdpFmtpLine.Split(';'))
            {
                string value = part.Trim();
                if (value.StartsWith("implementation_name=", System.StringComparison.Ordinal))
                    return value.Substring("implementation_name=".Length);
            }
            return null;
        }

        public static bool TrySize(string profile, out Vector2Int size)
        {
            if (profile == "1080p") { size = new Vector2Int(1920, 1080); return true; }
            if (profile == "1440p") { size = new Vector2Int(2560, 1440); return true; }
            size = default;
            return false;
        }
    }
}
