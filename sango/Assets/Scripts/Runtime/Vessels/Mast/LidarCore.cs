using UnityEngine;

namespace Sango.Vessels.Mast
{
    /// <summary>
    /// P3-S3 LiDAR scan pattern (spec #90; twin-bridge sensor_mode=lidar 点云视角).
    /// VLP-16-class sensor per the milliampere-ch5 §5.2 table: 16 lines, 10 Hz,
    /// 100 m range. The Unity visualization samples a mast-mounted pinhole depth
    /// camera (mount <see cref="MountId"/>, milliampere §4.2 flange row: 11 m
    /// above the waterline, mast centreline +2.1 m forward, 10° install downtilt
    /// for near-field coverage) and downsamples it to the 16-line × N-sample
    /// grid each frame.
    ///
    /// Mapping math (mirror of LidarPointCloud.shader, EditMode-tested like the
    /// IrTemperature/WhiteHot precedent): the 16 channels sit at the VLP-16
    /// elevations (-15°…+15°, 2° step) inside the depth camera's 32° vertical
    /// FOV (1° margin top/bottom), so channel i samples the depth texture row
    /// v = (2i+1)/32 — exact texel centres, point sampling, no interpolation
    /// skew. Horizontal samples are equal in the pinhole tan domain (equal
    /// pixel columns): u = (j+0.5)/N and the ray direction is the pixel ray
    /// ((2u-1)·tanHalfH, (2v-1)·tanHalfV, 1) — azimuth-equal-pixel, a documented
    /// deviation from the rotational equal-angle spacing (indistinguishable at
    /// 90° HFOV viz densities).
    /// </summary>
    public static class LidarPattern
    {
        /// <summary>Mast table mount id of the LiDAR depth camera (sensor-model-v1 §2/§3 vocabulary).</summary>
        public const string MountId = "mast_lidar";

        public const int ChannelCount = 16;          // VLP-16 lines
        public const float ChannelSpanDeg = 30f;     // vertical span ±15°
        public const float ChannelStepDeg = 2f;      // 16 × 2° = 30°
        public const int SamplesPerLine = 640;       // per-frame azimuth samples per line
        public const float FrameRateHz = 10f;        // milliampere §5.2 (VLP-16 5-20 Hz class)
        public const float MaxRangeM = 100f;         // nominal range clip (survey §2.3)
        public const float HorizontalFovDeg = 90f;   // v1 viz = forward 90° section (deviation note)

        /// <summary>Depth camera pinhole vertical FOV: channel span + 1° margin top/bottom (exact texel mapping).</summary>
        public const float DepthCameraFovDeg = 32f;

        /// <summary>Install downtilt (degrees, pitch negative = down; CameraPose semantics) for near-field coverage.</summary>
        public const float MountPitchDeg = -10f;

        /// <summary>Depth capture raster: 640 px wide; height realizes the 90°×32° pinhole (aspect = tan45°/tan16° ≈ 3.487 → 184 px).</summary>
        public const int DepthTextureWidthPx = 640;
        public const int DepthTextureHeightPx = 184;

        /// <summary>Points per frame = 16 × 640 (≈102k pts/s at 10 Hz, VLP-16 single-return class).</summary>
        public const int PointsPerFrame = ChannelCount * SamplesPerLine;

        /// <summary>Frame period (seconds; 10 Hz noise/pattern re-seed cadence).</summary>
        public static float FramePeriodS => 1f / FrameRateHz;

        /// <summary>VLP-16 channel elevation in degrees (camera-space; -15 + 2·i).</summary>
        public static float ChannelElevationDeg(int channel)
            => -0.5f * ChannelSpanDeg + ChannelStepDeg * channel;

        /// <summary>Depth-texture v coordinate of a channel (exact texel centre via the 32° FOV margin).</summary>
        public static float ChannelV(int channel)
            => (ChannelElevationDeg(channel) + 0.5f * DepthCameraFovDeg) / DepthCameraFovDeg;

        /// <summary>Depth-texture u coordinate of an azimuth sample (equal pixel columns).</summary>
        public static float SampleU(int sample) => (sample + 0.5f) / SamplesPerLine;

        /// <summary>Pixel ray direction of a (u, v) through the pinhole (camera space: +z forward).</summary>
        public static Vector3 RayDirection(float u, float v, float tanHalfH, float tanHalfV)
        {
            var direction = new Vector3((2f * u - 1f) * tanHalfH, (2f * v - 1f) * tanHalfV, 1f);
            return direction.normalized;
        }

        /// <summary>Relative bearing of a camera-space direction (degrees from the optical axis).</summary>
        public static float AzimuthDeg(Vector3 cameraSpaceDirection)
            => Mathf.Atan2(cameraSpaceDirection.x, cameraSpaceDirection.z) * Mathf.Rad2Deg;
    }

    /// <summary>
    /// P3-S3 LiDAR noise parameter table + pure math (spec #90; parameters copied
    /// from the survey §2.3 precedent table — CARLA dropoff/attenuation +
    /// AWSIM/RGL distance &amp; angle Gaussians; unity-sensor-sim-survey.md §2.3).
    /// Mirror of LidarPointCloud.shader (shader stays a thin port, IrWhiteHot
    /// precedent). Unity applies these per POINT (visual cloud); the backend
    /// LidarContactSensor is an independent synthetic model (bypass — point data
    /// never crosses the Unity↔backend boundary, sensor-model-v1 §1).
    /// </summary>
    public static class LidarNoise
    {
        // ── AWSIM/RGL distance Gaussian: σ_r(r) = base + rise·r (survey §2.3 row AWSIM) ──
        public const float RangeSigmaBaseM = 0.02f;
        /// <summary>Configurable rise term (survey: "rise per meter 可调", no pinned precedent value; 2 mm/m → 0.22 m σ at 100 m).</summary>
        public const float RangeSigmaRisePerM = 0.002f;

        // ── AWSIM/RGL angular Gaussian (survey §2.3: std 0.057°) ──
        public const float AngleSigmaDeg = 0.057f;

        // ── CARLA lidar dropoff + atmosphere (survey §2.3 row CARLA, documented defaults) ──
        public const float DropoffGeneralRate = 0.45f;
        public const float DropoffIntensityLimit = 0.8f;
        public const float DropoffZeroIntensity = 0.4f;
        public const float AtmosphereAttenuationPerM = 0.004f; // intensity ∝ 1 − a·d

        /// <summary>Point-cloud height ramp bounds (world y, metres): waterline band → mast-top band.</summary>
        public const float RampHeightMinM = -3f;
        public const float RampHeightMaxM = 15f;

        /// <summary>Range Gaussian sigma at a slant range (metres).</summary>
        public static float RangeSigma(float rangeM)
            => RangeSigmaBaseM + RangeSigmaRisePerM * Mathf.Max(0f, rangeM);

        /// <summary>Return intensity factor after atmospheric attenuation (CARLA linear a·d form).</summary>
        public static float IntensityFactor(float rangeM)
            => Mathf.Clamp01(1f - AtmosphereAttenuationPerM * Mathf.Max(0f, rangeM));

        /// <summary>
        /// Drop probability at a range (CARLA dropoff 概率随距离): while the
        /// attenuated intensity is above the drop limit the sweep is complete;
        /// beyond it, points drop at the general rate.
        /// </summary>
        public static float DropoutProbability(float rangeM)
            => IntensityFactor(rangeM) < DropoffIntensityLimit ? DropoffGeneralRate : 0f;

        /// <summary>Deterministic dropout decision from one uniform sample in [0,1).</summary>
        public static bool Dropout(float rangeM, float uniform01)
            => uniform01 < DropoutProbability(rangeM);

        /// <summary>Distance-gated point brightness (intensity floor = CARLA zero-intensity tag).</summary>
        public static float IntensityBrightness(float rangeM)
            => Mathf.Max(IntensityFactor(rangeM), DropoffZeroIntensity);

        /// <summary>
        /// Height ramp (normalized height 0-1 → RGB): deep water blue → teal →
        /// green → yellow → white; classic lidar viz colouring, monotonic
        /// luminance so ships/land/buoys read by elevation at a glance.
        /// </summary>
        private static readonly Color[] RampKeys =
        {
            new Color(0.05f, 0.10f, 0.35f), // deep (waterline band)
            new Color(0.00f, 0.55f, 0.55f), // teal (hull/freeboard)
            new Color(0.15f, 0.75f, 0.20f), // green (deck)
            new Color(0.90f, 0.80f, 0.10f), // yellow (superstructure)
            new Color(1.00f, 1.00f, 1.00f), // white (mast top)
        };

        public static Color HeightRamp(float t)
        {
            t = Mathf.Clamp01(t);
            int stops = RampKeys.Length - 1;
            float scaled = t * stops;
            int index = Mathf.Min((int)scaled, stops - 1);
            return Color.LerpUnclamped(RampKeys[index], RampKeys[index + 1], scaled - index);
        }

        /// <summary>Normalized ramp height of a world-space point.</summary>
        public static float RampT(float worldY)
            => Mathf.Clamp01((worldY - RampHeightMinM) / (RampHeightMaxM - RampHeightMinM));
    }
}
