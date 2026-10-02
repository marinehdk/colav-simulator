using System;

namespace Sango.Vessels.Mast
{
    /// <summary>Sensor channel of a mast mount (sensor-model-v1 §2 / observations-v1 §2 vocabulary).</summary>
    public enum MastSensorChannel
    {
        Eo = 2,     // camera_eo
        Ir = 3,     // camera_ir
        Lidar = 4,  // lidar (bypass channel — sensor-model-v1 §2; P3-S3 point-cloud view)
    }

    /// <summary>
    /// IR temperature tier (P3-S2 simplified model, plan裁决 3 "温度 tag+灰度 ramp"):
    /// 机舱/烟囱高、船体中、海面低、天空最低（milliampere-ch5 §3 + unity-sensor-sim-survey §3.3）。
    /// Values are the white-hot grayscale the tagged surface reads at (0-1).
    /// </summary>
    public enum IrTemperatureTier
    {
        Sky = 0,        // 0.05 — coldest
        Sea = 1,        // 0.15
        Deck = 2,       // 0.35
        Hull = 3,       // 0.50
        EngineRoom = 4, // 0.85
        Exhaust = 5,    // 1.00 — hottest
    }

    /// <summary>One mast sensor mount (calibration row).</summary>
    public struct MastMount
    {
        public string MountId;
        public MastSensorChannel Channel;
        public float AzimuthDeg;       // relative bearing from bow, compass-clockwise
        public float HFovDeg;          // horizontal field of view
        public int ReferenceWidthPx;   // intrinsics reference raster (fx scales with the frame)
        public int ReferenceHeightPx;
        public int PublishedWidthPx;   // raster the FramePublisher emits (0 = reference)
        public int PublishedHeightPx;
        public float HeightM;          // above the waterline (ship local +y)
        public float ForwardOffsetM;   // + forward of midship (ship local +z)
        public float StarboardOffsetM; // + starboard (ship local +x)
        public float PitchDeg;         // install downtilt (negative = down; 0 for the camera family, LiDAR only)

        public int FrameWidthPx => PublishedWidthPx > 0 ? PublishedWidthPx : ReferenceWidthPx;
        public int FrameHeightPx => PublishedHeightPx > 0 ? PublishedHeightPx : ReferenceHeightPx;
    }

    /// <summary>
    /// P3-S2 mast sensor family (spec #90): FCB45 mast anchor = FBX-measured air
    /// draught 12.98 m, mast at +2.1 m forward of midship
    /// (milliampere-ch5-fcb45-layout.md §3/§4.2). EO×5 ring (bow ±60° forward
    /// pair + beams 90°/270° + stern 180°, 90° HFOV) + IR×4 (bow/stbd/port/stern,
    /// 90° HFOV, 640×512 Boson-class) + PTZ dual spectrum ×2 channels (forward
    /// bracket +2.5 m; fixed mount in S2 — pan/tilt control out of segment).
    /// P3-S3 adds the LiDAR depth camera row (mast_lidar, milliampere §4.2
    /// flange row: 11 m above the waterline, 10° install downtilt for
    /// near-field blind-ring mitigation).
    ///
    /// Layout deviation note (frozen here + in the Python twin
    /// ``colav_simulator/core/mast_cameras.py``): the EO ring owns no mount at
    /// exactly 0° — the forward-looking EO role is the PTZ white channel
    /// (milliAmpere rationale: the forward role is the PTZ tele). With 90° HFOV
    /// the ring covers 15°-345°; the dead-ahead 30° sector is the PTZ's own
    /// coverage. The default detection feed mount is <see cref="FeedMountId"/>.
    /// The Python side (backend-authoritative calibration + georef) mirrors
    /// these constants; change both together (parity pinned by backend tests).
    /// </summary>
    public static class MastCameraTable
    {
        public const string FeedMountId = "mast_ptz_eo";
        public const int FeedWidthPx = 640;
        public const int FeedHeightPx = 480;

        public const float MastRailHeightM = 10.5f;
        public const float MastForwardOffsetM = 2.1f;
        public const float PtzBracketHeightM = 11.5f;
        public const float PtzForwardOffsetM = 2.5f;
        public const float LidarFlangeHeightM = 11.0f; // milliampere §4.2: 桅顶雷达下方法兰

        public static readonly MastMount[] Mounts =
        {
            // ── EO ring ×5 (90° HFOV, 1080p reference) ──
            new MastMount { MountId = "mast_eo_bow_stbd", Channel = MastSensorChannel.Eo, AzimuthDeg = 60f,
                HFovDeg = 90f, ReferenceWidthPx = 1920, ReferenceHeightPx = 1080,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            new MastMount { MountId = "mast_eo_bow_port", Channel = MastSensorChannel.Eo, AzimuthDeg = 300f,
                HFovDeg = 90f, ReferenceWidthPx = 1920, ReferenceHeightPx = 1080,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            new MastMount { MountId = "mast_eo_stbd", Channel = MastSensorChannel.Eo, AzimuthDeg = 90f,
                HFovDeg = 90f, ReferenceWidthPx = 1920, ReferenceHeightPx = 1080,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            new MastMount { MountId = "mast_eo_port", Channel = MastSensorChannel.Eo, AzimuthDeg = 270f,
                HFovDeg = 90f, ReferenceWidthPx = 1920, ReferenceHeightPx = 1080,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            new MastMount { MountId = "mast_eo_quarter", Channel = MastSensorChannel.Eo, AzimuthDeg = 180f,
                HFovDeg = 90f, ReferenceWidthPx = 1920, ReferenceHeightPx = 1080,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            // ── IR ring ×4 (90° HFOV, Boson-class 640×512) ──
            new MastMount { MountId = "mast_ir_bow", Channel = MastSensorChannel.Ir, AzimuthDeg = 0f,
                HFovDeg = 90f, ReferenceWidthPx = 640, ReferenceHeightPx = 512,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            new MastMount { MountId = "mast_ir_stbd", Channel = MastSensorChannel.Ir, AzimuthDeg = 90f,
                HFovDeg = 90f, ReferenceWidthPx = 640, ReferenceHeightPx = 512,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            new MastMount { MountId = "mast_ir_port", Channel = MastSensorChannel.Ir, AzimuthDeg = 270f,
                HFovDeg = 90f, ReferenceWidthPx = 640, ReferenceHeightPx = 512,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            new MastMount { MountId = "mast_ir_quarter", Channel = MastSensorChannel.Ir, AzimuthDeg = 180f,
                HFovDeg = 90f, ReferenceWidthPx = 640, ReferenceHeightPx = 512,
                HeightM = MastRailHeightM, ForwardOffsetM = MastForwardOffsetM },
            // ── PTZ dual spectrum ×1 (white + LWIR channels; forward bracket, fixed in S2) ──
            new MastMount { MountId = "mast_ptz_eo", Channel = MastSensorChannel.Eo, AzimuthDeg = 0f,
                HFovDeg = 60f, ReferenceWidthPx = 1920, ReferenceHeightPx = 1080,
                PublishedWidthPx = FeedWidthPx, PublishedHeightPx = FeedHeightPx,
                HeightM = PtzBracketHeightM, ForwardOffsetM = PtzForwardOffsetM },
            new MastMount { MountId = "mast_ptz_ir", Channel = MastSensorChannel.Ir, AzimuthDeg = 0f,
                HFovDeg = 45f, ReferenceWidthPx = 640, ReferenceHeightPx = 512,
                HeightM = PtzBracketHeightM, ForwardOffsetM = PtzForwardOffsetM },
            // ── LiDAR depth camera ×1 (P3-S3; milliampere §4.2 flange row: mast-top
            //    radar下方 11 m, mast centreline; 10° downtilt for the near-field role) ──
            new MastMount { MountId = LidarPattern.MountId, Channel = MastSensorChannel.Lidar, AzimuthDeg = 0f,
                HFovDeg = LidarPattern.HorizontalFovDeg, ReferenceWidthPx = LidarPattern.DepthTextureWidthPx,
                ReferenceHeightPx = LidarPattern.DepthTextureHeightPx,
                HeightM = LidarFlangeHeightM, ForwardOffsetM = MastForwardOffsetM, PitchDeg = LidarPattern.MountPitchDeg },
        };

        /// <summary>Table lookup by mount_id (contract observations-v1 §3 reference key).</summary>
        public static bool TryGet(string mountId, out MastMount mount)
        {
            foreach (var candidate in Mounts)
            {
                if (candidate.MountId == mountId)
                {
                    mount = candidate;
                    return true;
                }
            }
            mount = default;
            return false;
        }

        /// <summary>
        /// Ship-local position of a mount (ship frame: +z bow, +x starboard, +y
        /// up; origin at the waterline on midship — the FCB45 FBX origin
        /// convention, so parenting under the vessel root lands the heights).
        /// </summary>
        public static UnityEngine.Vector3 LocalPosition(in MastMount mount)
            => new UnityEngine.Vector3(mount.StarboardOffsetM, mount.HeightM, mount.ForwardOffsetM);

        /// <summary>
        /// Ship-local rotation of a mount camera: look along the mount azimuth
        /// with the mount pitch (level for the camera family — pitch 0; the
        /// LiDAR row carries its install downtilt). Unity rotation.y = azimuthDeg
        /// (yaw 0 = +z bow, positive = clockwise from above = toward +x
        /// starboard — the scene yaw convention); pitch follows the CameraPose
        /// semantics "negative = down" (CameraRig.ApplyPose: Unity Euler.x =
        /// −PitchDeg).
        /// </summary>
        public static UnityEngine.Quaternion LocalRotation(in MastMount mount)
            => UnityEngine.Quaternion.Euler(-mount.PitchDeg, mount.AzimuthDeg, 0f);

        /// <summary>True when the azimuth (relative bow, degrees) is inside the mount HFOV.</summary>
        public static bool CoversAzimuth(in MastMount mount, float azimuthDeg)
        {
            float delta = MathfRepeat(AzimuthDelta(azimuthDeg, mount.AzimuthDeg));
            return delta <= mount.HFovDeg * 0.5f;
        }

        /// <summary>Pinhole focal length in pixels from the horizontal FOV (square pixels).</summary>
        public static double FocalPx(in MastMount mount, int frameWidthPx)
            => (frameWidthPx / 2.0) / Math.Tan(mount.HFovDeg * Math.PI / 360.0);

        private static float AzimuthDelta(float a, float b)
        {
            float delta = (a - b) % 360f;
            if (delta > 180f) delta -= 360f;
            if (delta < -180f) delta += 360f;
            return delta;
        }

        private static float MathfRepeat(float value) => value < 0f ? -value : value;
    }

    /// <summary>
    /// IR temperature tag pure seams (spec #90): material/renderer-name → tier
    /// mapping and the white-hot ramp math mirrored by
    /// ``IrWhiteHot.shader`` (EditMode-tested; the shader stays a thin port).
    /// </summary>
    public static class IrTemperature
    {
        public const float SkyGray = 0.05f;
        public const float SeaGray = 0.15f;
        public const float DeckGray = 0.35f;
        public const float HullGray = 0.50f;
        public const float EngineRoomGray = 0.85f;
        public const float ExhaustGray = 1.00f;

        /// <summary>Grayscale a tier reads at in the white-hot view.</summary>
        public static float TierGray(IrTemperatureTier tier)
        {
            switch (tier)
            {
                case IrTemperatureTier.Exhaust: return ExhaustGray;
                case IrTemperatureTier.EngineRoom: return EngineRoomGray;
                case IrTemperatureTier.Hull: return HullGray;
                case IrTemperatureTier.Deck: return DeckGray;
                case IrTemperatureTier.Sea: return SeaGray;
                default: return SkyGray;
            }
        }

        /// <summary>
        /// Name-keyword → tier (pure; matches vessel part and scene material
        /// names). 机舱/烟囱高、船体中、甲板中低、海面低、天空最低；未命中按 Hull
        /// (船是热目标) — the applier registers vessel renderers only.
        /// </summary>
        public static IrTemperatureTier TierForMaterial(string materialOrRendererName)
        {
            string name = materialOrRendererName ?? string.Empty;
            string lower = name.ToLowerInvariant();
            if (ContainsAny(lower, "exhaust", "funnel", "stack", "smoke")) return IrTemperatureTier.Exhaust;
            if (ContainsAny(lower, "engine", "machinery", "vent")) return IrTemperatureTier.EngineRoom;
            if (ContainsAny(lower, "deck", "rail", "mast")) return IrTemperatureTier.Deck;
            if (ContainsAny(lower, "sea", "water", "ocean", "wave")) return IrTemperatureTier.Sea;
            if (ContainsAny(lower, "sky", "cloud")) return IrTemperatureTier.Sky;
            return IrTemperatureTier.Hull;
        }

        /// <summary>
        /// White-hot luminance ramp (mirror of IrWhiteHot.shader): gain, then
        /// gamma, both saturated — IR=黑白热像 simplified model.
        /// </summary>
        public static float WhiteHot(float luminance, float gain = 1.6f, float gamma = 0.8f)
        {
            float x = luminance * gain;
            x = x < 0f ? 0f : (x > 1f ? 1f : x);
            float shaped = (float)Math.Pow(x, gamma);
            return shaped < 0f ? 0f : (shaped > 1f ? 1f : shaped);
        }

        private static bool ContainsAny(string lower, params string[] keys)
        {
            foreach (string key in keys)
                if (lower.Contains(key)) return true;
            return false;
        }
    }
}
