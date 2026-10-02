using NUnit.Framework;
using Sango.Vessels.Mast;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P3-S3 LiDAR 点云纯函数测试（spec #90）。降采样数学（16 线×每线点数栅格、
    /// 针孔 uv→射线映射）+ 噪声参数表（survey §2.3 先例照抄：CARLA dropoff/
    /// 衰减 + AWSIM/RGL 距离与角度高斯）+ 高度 ramp——均与
    /// LidarPointCloud.shader 同式（C# 镜像可测，shader 薄端口工艺）。
    /// 机位行与后端权威标定（colav_simulator/core/mast_cameras.py mast_lidar 行）
    /// 双侧对齐，互钉测试同批更新。
    /// </summary>
    public class LidarPatternTests
    {
        [Test]
        public void ChannelGrid_MatchesVlp16Span()
        {
            Assert.That(LidarPattern.ChannelCount, Is.EqualTo(16), "16 线（VLP-16 级）");
            Assert.That(LidarPattern.ChannelElevationDeg(0), Is.EqualTo(-15f).Within(1e-5), "下缘 -15°");
            Assert.That(LidarPattern.ChannelElevationDeg(15), Is.EqualTo(+15f).Within(1e-5), "上缘 +15°");
            for (int channel = 1; channel < LidarPattern.ChannelCount; channel++)
                Assert.That(LidarPattern.ChannelElevationDeg(channel) - LidarPattern.ChannelElevationDeg(channel - 1),
                    Is.EqualTo(LidarPattern.ChannelStepDeg).Within(1e-5), $"channel {channel} 步距 2°");
        }

        [Test]
        public void DepthTextureMapping_IsExactTexelCentres()
        {
            // 32° FOV (±15° band + 1° margin): channel i samples v = (2i+1)/32.
            Assert.That(LidarPattern.ChannelV(0), Is.EqualTo(1f / 32f).Within(1e-6));
            Assert.That(LidarPattern.ChannelV(15), Is.EqualTo(31f / 32f).Within(1e-6));
            Assert.That(LidarPattern.ChannelV(7), Is.LessThan(0.5f));
            Assert.That(LidarPattern.ChannelV(8), Is.GreaterThan(0.5f), "光轴落在 channel 7/8 之间");
            Assert.That(LidarPattern.SampleU(0), Is.EqualTo(0.5f / LidarPattern.SamplesPerLine).Within(1e-9));
            Assert.That(LidarPattern.SampleU(639), Is.EqualTo(639.5f / LidarPattern.SamplesPerLine).Within(1e-9));
        }

        [Test]
        public void RayDirection_PinholeDomain_StaysInsideHorizontalFov()
        {
            float tanHalfH = Mathf.Tan(45f * Mathf.Deg2Rad); // 90° HFOV target texture
            float tanHalfV = Mathf.Tan(16f * Mathf.Deg2Rad); // 32° vertical
            Assert.That(LidarPattern.AzimuthDeg(LidarPattern.RayDirection(0.5f, 0.5f, tanHalfH, tanHalfV)),
                Is.EqualTo(0f).Within(1e-4), "画面中心 = 光轴");
            float azFirst = LidarPattern.AzimuthDeg(LidarPattern.RayDirection(LidarPattern.SampleU(0), 0.5f, tanHalfH, tanHalfV));
            float azLast = LidarPattern.AzimuthDeg(LidarPattern.RayDirection(LidarPattern.SampleU(639), 0.5f, tanHalfH, tanHalfV));
            Assert.That(azFirst, Is.InRange(-45f, -44f), "首采样在 -45° 近旁");
            Assert.That(azLast, Is.InRange(44f, 45f), "末采样在 +45° 近旁（针孔 tan 域不越 90° FOV）");
            float previous = azFirst;
            for (int s = 1; s < LidarPattern.SamplesPerLine; s += 16)
            {
                float azimuth = LidarPattern.AzimuthDeg(LidarPattern.RayDirection(LidarPattern.SampleU(s), 0.5f, tanHalfH, tanHalfV));
                Assert.That(azimuth, Is.GreaterThan(previous), "方位随采样序号单调");
                previous = azimuth;
            }
        }

        [Test]
        public void FrameBudget_MatchesMilliAmpereBaseline()
        {
            Assert.That(LidarPattern.FrameRateHz, Is.EqualTo(10f), "10 Hz（milliampere §5.2 基线）");
            Assert.That(LidarPattern.FramePeriodS, Is.EqualTo(0.1f).Within(1e-6));
            Assert.That(LidarPattern.MaxRangeM, Is.EqualTo(100f), "100 m 量程裁剪");
            Assert.That(LidarPattern.PointsPerFrame, Is.EqualTo(16 * 640), "16 线 × 每线 640 点");
            Assert.That(LidarPattern.MountPitchDeg, Is.EqualTo(-10f), "安装下倾 10°（近距补盲，CameraPose 负=俯）");
            Assert.That(LidarPattern.MountId, Is.EqualTo("mast_lidar"), "sensor-model-v1 §3 mount 词汇");
        }
    }

    public class LidarNoiseTests
    {
        [Test]
        public void RangeSigma_AwsimBasePlusRise()
        {
            Assert.That(LidarNoise.RangeSigma(0f), Is.EqualTo(0.02f).Within(1e-6), "AWSIM σ 基值 0.02 m");
            Assert.That(LidarNoise.RangeSigma(100f), Is.EqualTo(0.22f).Within(1e-6), "base + 0.002/m × 100 m");
            Assert.That(LidarNoise.RangeSigma(50f), Is.GreaterThan(LidarNoise.RangeSigma(10f)), "σ 随距离单调增");
            Assert.That(LidarNoise.RangeSigma(-5f), Is.EqualTo(0.02f).Within(1e-6), "负距离钳 0");
        }

        [Test]
        public void IntensityAndDropout_CarlaCurves()
        {
            Assert.That(LidarNoise.IntensityFactor(0f), Is.EqualTo(1f).Within(1e-6), "近距无衰减");
            Assert.That(LidarNoise.IntensityFactor(50f), Is.EqualTo(0.8f).Within(1e-6), "1 − 0.004×50 = drop 阈值");
            Assert.That(LidarNoise.IntensityFactor(100f), Is.EqualTo(0.6f).Within(1e-6));
            Assert.That(LidarNoise.DropoutProbability(40f), Is.EqualTo(0f).Within(1e-6), "衰减未到 limit → 不丢点");
            Assert.That(LidarNoise.DropoutProbability(60f), Is.EqualTo(0.45f).Within(1e-6), "过 limit → CARLA general rate");
            Assert.That(LidarNoise.Dropout(40f, 0f), Is.False, "闸内恒保留");
            Assert.That(LidarNoise.Dropout(60f, 0.44f), Is.True, "rate 0.45 以下 → 丢");
            Assert.That(LidarNoise.Dropout(60f, 0.46f), Is.False, "rate 0.45 以上 → 留");
        }

        [Test]
        public void IntensityBrightness_FloorsAtCarlaZeroIntensity()
        {
            Assert.That(LidarNoise.IntensityBrightness(0f), Is.EqualTo(1f).Within(1e-6));
            Assert.That(LidarNoise.IntensityBrightness(1000f), Is.EqualTo(LidarNoise.DropoffZeroIntensity).Within(1e-6),
                "远端亮度下限 = CARLA zero-intensity 标签");
        }

        [Test]
        public void HeightRamp_MonotonicLuminanceDeepToWhite()
        {
            Assert.That(LidarNoise.HeightRamp(1f), Is.EqualTo(new Color(1f, 1f, 1f)).Within(1e-5), "最高 = 白");
            float previous = Luminance(LidarNoise.HeightRamp(0f));
            for (float t = 0.02f; t <= 1f; t += 0.02f)
            {
                float current = Luminance(LidarNoise.HeightRamp(t));
                Assert.That(current, Is.GreaterThanOrEqualTo(previous - 1e-5), $"ramp 亮度单调 t={t:0.00}");
                previous = current;
            }
        }

        [Test]
        public void RampT_ClampsToWorldHeightWindow()
        {
            Assert.That(LidarNoise.RampT(LidarNoise.RampHeightMinM - 5f), Is.EqualTo(0f).Within(1e-6));
            Assert.That(LidarNoise.RampT(LidarNoise.RampHeightMaxM + 5f), Is.EqualTo(1f).Within(1e-6));
            Assert.That(LidarNoise.RampT(0f), Is.EqualTo((0f - LidarNoise.RampHeightMinM)
                / (LidarNoise.RampHeightMaxM - LidarNoise.RampHeightMinM)).Within(1e-6), "水线落在窗口内");
        }

        static float Luminance(Color color) => 0.2126f * color.r + 0.7152f * color.g + 0.0722f * color.b;
    }

    public class LidarMountRowTests
    {
        [Test]
        public void MastLidarRow_MatchesBackendAuthoritativeCalibration()
        {
            Assert.That(MastCameraTable.TryGet("mast_lidar", out var lidar), Is.True, "P3-S3 机位行");
            Assert.That(lidar.Channel, Is.EqualTo(MastSensorChannel.Lidar));
            Assert.That((int)lidar.Channel, Is.EqualTo(4), "sensor_id=4（sensor-model-v1 §2 词汇）");
            Assert.That(lidar.AzimuthDeg, Is.EqualTo(0f), "桅杆中纵剖面");
            Assert.That(lidar.HFovDeg, Is.EqualTo(90f), "v1 可视化 = 前向 90° 扇区（偏差写档）");
            Assert.That(lidar.HeightM, Is.EqualTo(11.0f), "桅顶下法兰 11 m（milliampere §4.2，后端同字面量互钉）");
            Assert.That(lidar.ForwardOffsetM, Is.EqualTo(2.1f));
            Assert.That(lidar.PitchDeg, Is.EqualTo(-10f), "安装下倾 10°");
            Assert.That(lidar.ReferenceWidthPx, Is.EqualTo(640), "深度栅格宽（Unity/后端同字面量）");
            Assert.That(lidar.ReferenceHeightPx, Is.EqualTo(184), "深度栅格高 = 90°×32° 针孔纵横比（tan45/tan16）");
        }

        [Test]
        public void LidarMountPose_CarriesDowntilt()
        {
            Assert.That(MastCameraTable.TryGet("mast_lidar", out var lidar), Is.True);
            Assert.That(MastCameraTable.LocalPosition(lidar), Is.EqualTo(new Vector3(0f, 11f, 2.1f)));
            Vector3 look = MastCameraTable.LocalRotation(lidar) * Vector3.forward;
            float pitchRad = LidarPattern.MountPitchDeg * Mathf.Deg2Rad;
            var expectedLook = new Vector3(0f, Mathf.Sin(pitchRad), Mathf.Cos(pitchRad));
            Assert.That(Vector3.Angle(look, expectedLook), Is.LessThan(0.01f),
                $"前视绕 +x 下倾 10°（俯）；look={look} expected={expectedLook}");
            Assert.That(Mathf.Abs(look.x), Is.LessThan(1e-4), "下倾在中纵剖面内");
            Assert.That(look.y, Is.LessThan(0f), "俯视（y 分量为负）");
            // Blind-ring consequence of the tilt: lower edge -25° → 11/tan(25°) ≈ 23.6 m.
            float lowerEdgeDeg = Mathf.Abs(LidarPattern.MountPitchDeg) + LidarPattern.ChannelSpanDeg * 0.5f;
            Assert.That(lowerEdgeDeg, Is.EqualTo(25f).Within(1e-5));
            Assert.That(11f / Mathf.Tan(lowerEdgeDeg * Mathf.Deg2Rad), Is.EqualTo(23.59f).Within(0.05f),
                "下倾后近端盲环 ≈23.6 m（milliampere §4.3 近距补盲定位）");
        }
    }
}
