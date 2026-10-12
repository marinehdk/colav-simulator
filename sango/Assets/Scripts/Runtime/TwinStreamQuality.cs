using Unity.RenderStreaming;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>Local WEB capture profiles; no simulation or replay-clock authority.</summary>
    public sealed class TwinStreamQuality
    {
        readonly VideoStreamSender m_Sender;
        public static readonly string[] Profiles = { "1080p", "1440p" };
        public string Profile { get; private set; }

        public TwinStreamQuality(VideoStreamSender sender)
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
                // Avoid history trails as water normals and the follow camera move.
                hd.antialiasing = HDAdditionalCameraData.AntialiasingMode.SubpixelMorphologicalAntiAliasing;
            }
            if (Application.isPlaying)
            {
                Application.runInBackground = true;
                QualitySettings.vSyncCount = 0;
                // Render above the 30 fps capture clock: the sender's 30 fps
                // ticker then always samples a fresh, evenly spaced frame and
                // absorbs render-side jitter. Capping render at 30 made the
                // stream breathe at 27.8-29.5 fps, which reads as visible
                // stutter on the water surface (uneven 2:1 pacing on 60 Hz).
                Application.targetFrameRate = 60;
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
