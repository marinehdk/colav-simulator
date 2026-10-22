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
    /// IR temperature tier (P3-S2 simplified model, plan裁决 3 "温度 tag+灰度 ramp";
    /// P2 IR realism round adds the ambient Land tier):
    /// 机舱/烟囱高、船体中、甲板中低、海面低、环境地形/岸线/桥 Land 略高于海
    /// （白天储热陆地常比海面暖，survey 2026-10-19-sitaw-ir-latency-realism §4 #7）、
    /// 天空最低（milliampere-ch5 §3 + unity-sensor-sim-survey §3.3）。
    /// Values are the white-hot grayscale the tagged surface reads at (0-1).
    /// Land appends at 6 (not between Sea/Deck) to keep the frozen P3-S2 ordinals.
    /// </summary>
    public enum IrTemperatureTier
    {
        Sky = 0,        // 0.05 — coldest
        Sea = 1,        // 0.15
        Deck = 2,       // 0.35
        Hull = 3,       // 0.50
        EngineRoom = 4, // 0.85
        Exhaust = 5,    // 1.00 — hottest
        Land = 6,       // 0.20 — ambient terrain/shoreline/bridge (P2 IR realism)
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
        public const float LandGray = 0.20f;
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
                case IrTemperatureTier.Land: return LandGray;
                case IrTemperatureTier.Sea: return SeaGray;
                default: return SkyGray;
            }
        }

        /// <summary>
        /// Name-keyword → tier (pure; matches vessel part and scene material
        /// names). 机舱/烟囱高、船体中、甲板中低、环境地形/岸线/桥 Land、海面低、
        /// 天空最低；未命中按 Hull (船是热目标) — the applier registers vessel
        /// renderers only. Land keywords sit after the vessel-part keywords so
        /// e.g. a vessel "Bridge Deckhouse" renderer still lands on a vessel
        /// tier when it carries a part keyword, and before Sea/Sky so the
        /// shared Cesium landscape material ("…Landscape…") hits Land.
        /// </summary>
        public static IrTemperatureTier TierForMaterial(string materialOrRendererName)
        {
            string name = materialOrRendererName ?? string.Empty;
            string lower = name.ToLowerInvariant();
            if (ContainsAny(lower, "exhaust", "funnel", "stack", "smoke")) return IrTemperatureTier.Exhaust;
            if (ContainsAny(lower, "engine", "machinery", "vent")) return IrTemperatureTier.EngineRoom;
            if (ContainsAny(lower, "deck", "rail", "mast")) return IrTemperatureTier.Deck;
            if (ContainsAny(lower, "land", "terrain", "ground", "shore", "coast", "island", "building", "bridge", "rock"))
                return IrTemperatureTier.Land;
            if (ContainsAny(lower, "sea", "water", "ocean", "wave")) return IrTemperatureTier.Sea;
            if (ContainsAny(lower, "sky", "cloud")) return IrTemperatureTier.Sky;
            return IrTemperatureTier.Hull;
        }

        /// <summary>
        /// White-hot luminance ramp (mirror of IrWhiteHot.shader): gain, then
        /// gamma, both saturated — IR=黑白热像 simplified model. Default gain
        /// 1.0 = tier-faithful calibration (every tier keeps its level through
        /// the 0.8-gamma ramp); the AGC breathes ±25% around it (AgcGain).
        /// </summary>
        public static float WhiteHot(float luminance, float gain = 1.0f, float gamma = 0.8f)
        {
            float x = luminance * gain;
            x = x < 0f ? 0f : (x > 1f ? 1f : x);
            float shaped = (float)Math.Pow(x, gamma);
            return shaped < 0f ? 0f : (shaped > 1f ? 1f : shaped);
        }

        /// <summary>
        /// AGC EMA step (P2 IR realism; mirror of the IrViewPass main-thread
        /// servo): exponential approach of the smoothed scene mean toward the
        /// raw readback mean with time constant <paramref name="tauSeconds"/>
        /// (~0.8s) — hot sources entering the frame shift the gain over ~a
        /// second (AGC "breathing"), never within one frame (review: no
        /// temporal constant ⇒ per-frame gain flicker). Pure, EditMode-tested.
        /// </summary>
        public static float AgcStep(float smoothed, float raw, float dt, float tauSeconds = 0.8f)
        {
            float tau = tauSeconds > 1e-4f ? tauSeconds : 1e-4f;
            float alpha = dt < 0f ? 0f : (dt / tau > 1f ? 1f : dt / tau);
            return smoothed + (raw - smoothed) * alpha;
        }

        /// <summary>
        /// AGC gain from the servo mean (mirror of the IrWhiteHot.shader clamp):
        /// home = unity at the sea/sky target mean, clamped 0.8-1.25 so the six
        /// P3-S2 temperature tiers never collapse into saturated white (review:
        /// unclamped stacking with the static gain reached 2.7-3.5× ⇒ only
        /// sky/sea/ship-white three levels survived).
        /// </summary>
        public static float AgcGain(float targetMean, float measuredMean)
        {
            float mean = measuredMean > 1e-3f ? measuredMean : 1e-3f;
            float gain = targetMean / mean;
            return gain < 0.8f ? 0.8f : (gain > 1.25f ? 1.25f : gain);
        }

        /// <summary>
        /// Polarity mapping (P2 IR realism; mirror of IrWhiteHot.shader final
        /// lerp, survey §4 #1 — M232 white hot/black hot): white-hot = identity,
        /// black-hot = inverted display of the same sensor data.
        /// </summary>
        public static float DisplayGray(float whiteHotGray, bool blackHot)
            => blackHot ? 1f - whiteHotGray : whiteHotGray;

        /// <summary>
        /// Unity Euler x → domain pitch in degrees (domain convention shared by
        /// CameraViews/<see cref="HorizonScreenY"/>: NEGATIVE = down). Unity
        /// Quaternion.Euler is POSITIVE x = down — Rx(+90)·(0,0,1) = (0,−1,0)
        /// (CameraRig.ApplyPose root-cause note 2026-09-28) — so crossing the
        /// boundary NEGATES. Normalizes the [0,360) euler wrap first (333.4° is
        /// a 26.6° UP look, not a 333° pitch). P2 review fix: IrViewPass.Execute
        /// previously fed Unity euler x straight into HorizonScreenY, inverting
        /// the horizon (chase Unity x=+26.6 read as 26.6 UP → horizonY 0.066
        /// instead of 0.934 → 83% of the frame flattened to cold sky gray).
        /// Pure seam so the EditMode tests can pin the call-site sign.
        /// </summary>
        public static float PitchFromUnityEulerX(float unityEulerXDeg)
        {
            float euler = unityEulerXDeg % 360f;
            if (euler > 180f) euler -= 360f;
            else if (euler < -180f) euler += 360f;
            return -euler;
        }

        /// <summary>
        /// Horizon screen height (uv.y, 0=bottom 1=top; may fall outside [0,1]
        /// when the horizon is off-screen) for a pinhole camera looking with
        /// pitch/vertical-FOV — P2 IR realism horizon cold-sky gradient seam.
        /// Elevation-0 rays project to NDC y = tan(−pitch)/tan(vFov/2) →
        /// uv=(ndc+1)/2. Lives here (not IrViewPass) so the EditMode tests can
        /// reach it — IrViewPass.cs compiles into Assembly-CSharp (CustomPass
        /// subclass outside the Sango.Vessels asmdef, LidarViewPass precedent)
        /// which the test assembly cannot reference. Roll assumed level.
        /// </summary>
        public static float HorizonScreenY(float pitchDeg, float verticalFovDeg)
        {
            float halfFovTan = (float)Math.Tan(Math.Clamp(verticalFovDeg, 1.0, 179.0) * Math.PI / 360.0);
            if (halfFovTan < 1e-4f) halfFovTan = 1e-4f;
            float ndc = -(float)Math.Tan(Math.Clamp(pitchDeg, -89.0, 89.0) * Math.PI / 180.0) / halfFovTan;
            return (ndc + 1f) * 0.5f;
        }

        private static bool ContainsAny(string lower, params string[] keys)
        {
            foreach (string key in keys)
                if (lower.Contains(key)) return true;
            return false;
        }
    }
}
