using System;
using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// RadarPpiMath 纯函数测试(00-REPORT §5/§6 P2;镜像三源:web radar-ppi.js /
    /// radar-video.js raster() / 后端 radar_video.py——期望值全部钉 web/后端公式,
    /// Unity 屏与 web 屏逐 spoke 对拍的公式基准面)。
    /// </summary>
    public class RadarPpiMathTests
    {
        const double Tolerance = 1e-9;

        [Test]
        public void RangeRings_ThirdsPlusOuter_MirrorsWebRangeRingsM()
        {
            // web radar-ppi.js:157-160 rangeRingsM:[scale/3, 2·scale/3, scale]
            double[] rings = RadarPpiMath.RangeRingRadiiM(3000.0);
            Assert.That(rings.Length, Is.EqualTo(3));
            Assert.That(rings[0], Is.EqualTo(1000.0).Within(Tolerance));
            Assert.That(rings[1], Is.EqualTo(2000.0).Within(Tolerance));
            Assert.That(rings[2], Is.EqualTo(3000.0).Within(Tolerance));
            Assert.That(RadarPpiMath.RangeRingRadiiM(0.0), Is.Empty, "非正量程回空(同款守卫)");
        }

        [Test]
        public void BearingTicks_CardinalAtQuadrants()
        {
            // web radar-ppi.js:348:deg % 90 == 0 → 加长刻度
            Assert.That(RadarPpiMath.IsCardinalTick(0), Is.True);
            Assert.That(RadarPpiMath.IsCardinalTick(90), Is.True);
            Assert.That(RadarPpiMath.IsCardinalTick(180), Is.True);
            Assert.That(RadarPpiMath.IsCardinalTick(270), Is.True);
            Assert.That(RadarPpiMath.IsCardinalTick(30), Is.False);
            Assert.That(RadarPpiMath.IsCardinalTick(330), Is.False);
        }

        [Test]
        public void AfterglowDecay_097PerFrameAt60Fps_Reference()
        {
            // 00-REPORT §5 底图层"0.97/帧"——按 60 fps 换算为 sim_time 年龄纯函数(帧率无关)。
            Assert.That(RadarPpiMath.AfterglowDecay(0.0), Is.EqualTo(1.0).Within(Tolerance));
            Assert.That(RadarPpiMath.AfterglowDecay(1.0 / 60.0), Is.EqualTo(0.97).Within(1e-12), "一参考帧 = 0.97");
            Assert.That(RadarPpiMath.AfterglowDecay(1.0), Is.EqualTo(Math.Pow(0.97, 60.0)).Within(Tolerance));
            Assert.That(RadarPpiMath.AfterglowDecay(-3.0), Is.EqualTo(1.0).Within(Tolerance), "负龄钳 1(未采集行另有门)");
        }

        [Test]
        public void VideoDisplayValue_GainSeaRain_MirrorsWebRasterFormula()
        {
            // web radar-video.js:97-98 逐式:value = clamp(u8 + gain·2 − (sea·0.6·e^(−r/1800) + rain·0.3), 0, 255)
            Assert.That(RadarPpiMath.VideoDisplayValue(100, 0, 0, 0, 0.0), Is.EqualTo(100.0).Within(Tolerance));
            Assert.That(RadarPpiMath.VideoDisplayValue(100, 10, 0, 0, 0.0), Is.EqualTo(120.0).Within(Tolerance), "gain·2");
            Assert.That(RadarPpiMath.VideoDisplayValue(100, -20, 0, 0, 0.0), Is.EqualTo(60.0).Within(Tolerance), "负 gain");
            Assert.That(RadarPpiMath.VideoDisplayValue(100, 0, 50, 0, 0.0), Is.EqualTo(70.0).Within(Tolerance), "sea 近程全抑制");
            Assert.That(RadarPpiMath.VideoDisplayValue(100, 0, 50, 0, 1800.0),
                Is.EqualTo(100.0 - 50.0 * 0.6 * Math.Exp(-1.0)).Within(Tolerance), "sea 随距离衰减");
            Assert.That(RadarPpiMath.VideoDisplayValue(100, 0, 0, 100, 0.0), Is.EqualTo(70.0).Within(Tolerance), "rain 恒定抑制");
            Assert.That(RadarPpiMath.VideoDisplayValue(0, 0, 0, 100, 0.0), Is.EqualTo(0.0).Within(Tolerance), "下限钳 0");
            Assert.That(RadarPpiMath.VideoDisplayValue(250, 20, 0, 0, 0.0), Is.EqualTo(255.0).Within(Tolerance), "上限钳 255");
        }

        [Test]
        public void DisplayRotation_HuNu_MirrorsWebRotation()
        {
            // web radar-ppi.js:251 rotation():headingUp ? heading : 0(CU 为 backlog)
            Assert.That(RadarPpiMath.DisplayRotationRad(false, 1.234), Is.EqualTo(0.0).Within(Tolerance), "NU = 0");
            Assert.That(RadarPpiMath.DisplayRotationRad(true, 1.234), Is.EqualTo(1.234).Within(Tolerance), "HU = 艏向");
        }

        [Test]
        public void EblDisplayAngle_TrueBearingMinusRotation_WrapsPositive()
        {
            // web radar-ppi.js:400 bearing = eblDeg·π/180 − rotation()
            Assert.That(RadarPpiMath.EblDisplayAngleRad(90.0, Math.PI / 2.0), Is.EqualTo(0.0).Within(Tolerance),
                "HU 艏向东 + EBL 090°T = 屏正上");
            Assert.That(RadarPpiMath.EblDisplayAngleRad(0.0, Math.PI / 2.0),
                Is.EqualTo(3.0 * Math.PI / 2.0).Within(Tolerance), "负角 wrap 到 [0,2π)");
            Assert.That(RadarPpiMath.EblDisplayAngleRad(350.0, 0.3),
                Is.EqualTo(RadarPpiMath.WrapPositive(350.0 * Math.PI / 180.0 - 0.3)).Within(Tolerance));
        }

        [Test]
        public void Vrm_VisibilityAndFraction_MirrorsWeb()
        {
            // web radar-ppi.js:397 vrmNm > 0 && vrmNm <= rangeScaleNm
            Assert.That(RadarPpiMath.VrmVisible(0.0, 6.0), Is.False);
            Assert.That(RadarPpiMath.VrmVisible(0.75, 6.0), Is.True);
            Assert.That(RadarPpiMath.VrmVisible(6.0, 6.0), Is.True, "恰在量程 = 在内");
            Assert.That(RadarPpiMath.VrmVisible(6.1, 6.0), Is.False, "出量程隐藏");
            Assert.That(RadarPpiMath.VrmRadiusFraction(0.75, 6.0), Is.EqualTo(0.125).Within(Tolerance));
            Assert.That(RadarPpiMath.VrmRadiusFraction(0.75, 0.0), Is.EqualTo(0.0).Within(Tolerance));
        }

        [Test]
        public void SweepDisplayAngle_PhaseMinusRotation_MirrorsWebSweepCanvas()
        {
            // web radar-ppi.js:322 sweepCanvas = sweepAz − … − rotation();相位本体 = sweepAzimuthRad
            double quarter = RadarPpiMath.SweepDisplayAngleRad(0.625, 2.5, 0.0);
            Assert.That(quarter, Is.EqualTo(Math.PI / 2.0).Within(Tolerance), "NU 1/4 转 = 90°");
            Assert.That(RadarPpiMath.SweepDisplayAngleRad(0.625, 2.5, Math.PI / 2.0),
                Is.EqualTo(0.0).Within(Tolerance), "HU(艏向东)同刻扫线在屏上");
            double wrapped = RadarPpiMath.SweepDisplayAngleRad(0.0, 2.5, 0.5);
            Assert.That(wrapped, Is.EqualTo(2.0 * Math.PI - 0.5).Within(Tolerance), "负角 wrap 正");
        }

        [Test]
        public void BlipDisplayNormalized_RotationAndInside_MirrorsWeb()
        {
            // web radar-ppi.js:368-371 旋转式 + ppiProject:146-154 inside(≤ 1 含边界)
            Assert.That(RadarPpiMath.BlipDisplayNormalized(1000.0, 0.0, 2000.0, 0.0, out double n, out double e), Is.True);
            Assert.That(n, Is.EqualTo(1000.0).Within(Tolerance));
            Assert.That(e, Is.EqualTo(0.0).Within(Tolerance));

            // HU 艏向东(π/2):正北目标 → 屏左(e = −n·sin = −1000)——北在艏向左侧,几何正解
            Assert.That(RadarPpiMath.BlipDisplayNormalized(1000.0, 0.0, 2000.0, Math.PI / 2.0, out n, out e), Is.True);
            Assert.That(n, Is.EqualTo(0.0).Within(1e-9));
            Assert.That(e, Is.EqualTo(-1000.0).Within(Tolerance));

            Assert.That(RadarPpiMath.BlipDisplayNormalized(2000.0, 0.0, 2000.0, 0.0, out _, out _), Is.True, "恰在量程 = 盘内");
            Assert.That(RadarPpiMath.BlipDisplayNormalized(2001.0, 0.0, 2000.0, 0.0, out _, out _), Is.False, "出量程 = 隐藏");
        }

        [Test]
        public void Intensity_ExcessSlope_MirrorsWebPpiIntensity()
        {
            // web radar-ppi.js:77-80 ppiIntensity:clamp(x/18, 0.08, 1) 斜率/下限同值
            Assert.That(RadarPpiMath.IntensityFromExcessDb(0.0), Is.EqualTo(0.08).Within(Tolerance), "下限 0.08");
            Assert.That(RadarPpiMath.IntensityFromExcessDb(9.0), Is.EqualTo(0.5).Within(Tolerance));
            Assert.That(RadarPpiMath.IntensityFromExcessDb(18.0), Is.EqualTo(1.0).Within(Tolerance));
            Assert.That(RadarPpiMath.IntensityFromExcessDb(-5.0), Is.EqualTo(0.08).Within(Tolerance));
            Assert.That(RadarPpiMath.IntensityFromExcessDb(30.0), Is.EqualTo(1.0).Within(Tolerance), "上限 1");
        }

        [Test]
        public void LinearPower_InvertsBackendVideoMapping()
        {
            // 后端 radar_video.py:130 video = clip((10·log10(p)+10)·255/70) 的逆:LUT[v] = 10^((v·70/255−10)/10)
            Assert.That(RadarPpiMath.LinearPower(0), Is.EqualTo(0.1).Within(1e-12), "u8=0 → 10^(−1)");
            Assert.That(RadarPpiMath.LinearPower(255), Is.EqualTo(1e6).Within(1.0), "u8=255 → 10^6");
            for (int v = 0; v <= 255; v += 17)
                Assert.That(RadarPpiMath.LinearPower((byte)v),
                    Is.EqualTo(Math.Pow(10.0, (v * 70.0 / 255.0 - 10.0) / 10.0)).Within(1e-9), $"LUT[{v}]");
        }

        [Test]
        public void CaCfarRows_PeakOverFlatNoise_EdgesHaveNoClaim()
        {
            // 结构镜像 radar_video.py ca_cfar:48-65:平坦噪声不过 alpha·noise 门,尖峰过;
            // 边缘 bin(margin = guard+training 内)无门限主张 = false/∞。
            const int spokes = 4, bins = 40, guard = 3, training = 12;
            var video = new byte[spokes * bins];
            for (int i = 0; i < video.Length; i++) video[i] = 30;
            video[1 * bins + 20] = 250; // row 1 尖峰
            var mask = new bool[video.Length];
            var threshold = new double[video.Length];

            RadarPpiMath.CaCfarRows(video, spokes, bins, 0, spokes, 1e-4, guard, training, mask, threshold);

            Assert.That(bins, Is.EqualTo(2 * (guard + training) + 10), "宽栅格前提(> 2·margin)");
            Assert.That(mask[1 * bins + 20], Is.True, "尖峰过门限");
            Assert.That(mask[1 * bins + 19], Is.False, "邻近 bin 被保护单元隔开:训练窗不含尖峰 → 门限仍 alpha·平坦,平坦值不过门(radar_video.py ca_cfar 逐 bin 独立判定,无峰值扩展)");
            Assert.That(mask[0 * bins + 20], Is.False, "噪声行全不过(平坦 < alpha·mean)");
            Assert.That(mask[1 * bins + 5], Is.False);
            Assert.That(mask[1 * bins + 10], Is.False, "边缘 bin(margin 内)无主张");
            Assert.That(threshold[1 * bins + 10], Is.EqualTo(double.PositiveInfinity), "边缘门限 = ∞");
            Assert.That(threshold[1 * bins + 20], Is.GreaterThan(0.0), "主张域门限有限");
            // alpha 公式:2·training·(pfa^(−1/(2·training)) − 1) ≈ 11.23(pfa=1e-4, training=12)
            double alpha = 2 * training * (Math.Pow(1e-4, -1.0 / (2 * training)) - 1);
            double noise = RadarPpiMath.LinearPower(30);
            Assert.That(threshold[1 * bins + 20], Is.EqualTo(alpha * noise).Within(1e-6 * alpha * noise),
                "门限 = alpha·训练窗均值");
        }

        [Test]
        public void CaCfarRows_NarrowGrid_DegenerateNoClaim()
        {
            // bins ≤ 2·margin:全部无主张(后端 width<=2*margin 早退同语义)
            const int spokes = 2, bins = 30, guard = 3, training = 12; // 30 ≤ 2·15
            var video = new byte[spokes * bins];
            for (int i = 0; i < video.Length; i++) video[i] = 255;
            var mask = new bool[video.Length];
            var threshold = new double[video.Length];
            RadarPpiMath.CaCfarRows(video, spokes, bins, 0, spokes, 1e-4, guard, training, mask, threshold);
            for (int i = 0; i < mask.Length; i++)
            {
                Assert.That(mask[i], Is.False, $"bin {i}");
                Assert.That(threshold[i], Is.EqualTo(double.PositiveInfinity));
            }
        }

        [Test]
        public void CaCfarRows_RejectsInvalidSlice()
        {
            var video = new byte[4 * 40];
            var mask = new bool[video.Length];
            var threshold = new double[video.Length];
            Assert.Throws<ArgumentOutOfRangeException>(() =>
                RadarPpiMath.CaCfarRows(video, 4, 40, 2, 1, 1e-4, 3, 12, mask, threshold), "rowEnd ≤ rowStart");
            Assert.Throws<ArgumentOutOfRangeException>(() =>
                RadarPpiMath.CaCfarRows(video, 4, 40, 0, 5, 1e-4, 3, 12, mask, threshold), "rowEnd 越界");
        }

        [Test]
        public void ClusterDetections_CentroidWeightingExcessAndCap_BackendMirror()
        {
            // 镜像 radar_video.py _detections:271-315:4-连通簇 → 功率加权质心 →
            // excess = 10·log10(峰值/平均门限);cap 截断且总簇数照报。
            const int spokes = 8, bins = 64;
            const double rangeM = 640.0;
            var video = new byte[spokes * bins];
            for (int i = 0; i < video.Length; i++) video[i] = 10;
            video[2 * bins + 30] = 200; // 簇 1:row 2 bins 30-31
            video[2 * bins + 31] = 200;
            video[5 * bins + 40] = 150; // 簇 2:row 5 bin 40
            var mask = new bool[video.Length];
            var threshold = new double[video.Length];
            // 掩膜直接手工构造(CFAR 本体另有测试):两簇单元置 true
            mask[2 * bins + 30] = true;
            mask[2 * bins + 31] = true;
            mask[5 * bins + 40] = true;
            for (int i = 0; i < threshold.Length; i++) threshold[i] = RadarPpiMath.LinearPower(10) * 2.0;

            var origins = new double[spokes][];
            for (int r = 0; r < spokes; r++) origins[r] = new[] { 1000.0, 2000.0 };

            var results = new List<RadarPpiDetection>();
            int found = RadarPpiMath.ClusterDetections(video, mask, threshold, spokes, bins,
                origins, null, rangeM, 400, results);
            Assert.That(found, Is.EqualTo(2));
            Assert.That(results.Count, Is.EqualTo(2));

            // 簇 1 质心:bearing = row·2π/spokes(rowBearings 缺失回退),bin 中心距离加权平均 = 310 m
            double bearing = RadarSpokeDecoder.RowBearingRad(2, spokes);
            double expectedRange = 0.5 * (RadarSpokeDecoder.BinRangeM(30, bins, rangeM)
                                          + RadarSpokeDecoder.BinRangeM(31, bins, rangeM));
            Assert.That(results[0].CellCount, Is.EqualTo(2));
            Assert.That(results[0].NorthM, Is.EqualTo(1000.0 + Math.Cos(bearing) * expectedRange).Within(1e-6));
            Assert.That(results[0].EastM, Is.EqualTo(2000.0 + Math.Sin(bearing) * expectedRange).Within(1e-6));
            Assert.That(results[0].ExcessDb, Is.GreaterThan(0.0), "尖峰 > 门限 → 正 excess");
            Assert.That(results[0].Intensity, Is.EqualTo(RadarPpiMath.IntensityFromExcessDb(results[0].ExcessDb)).Within(Tolerance));
            Assert.That(results[1].CellCount, Is.EqualTo(1));

            // 消费即清:掩膜全 false(防重入)
            for (int i = 0; i < mask.Length; i++) Assert.That(mask[i], Is.False, $"mask[{i}]");

            // cap = 1:found 2 照报,results 1
            results.Clear();
            mask[2 * bins + 30] = true;
            mask[2 * bins + 31] = true;
            mask[5 * bins + 40] = true;
            found = RadarPpiMath.ClusterDetections(video, mask, threshold, spokes, bins,
                origins, null, rangeM, 1, results);
            Assert.That(found, Is.EqualTo(2));
            Assert.That(results.Count, Is.EqualTo(1), "超 cap 截断(后端 break 同语义)");
        }

        [Test]
        public void ClusterDetections_EmptyMask_ReturnsZero()
        {
            var video = new byte[64];
            var results = new List<RadarPpiDetection>();
            Assert.That(RadarPpiMath.ClusterDetections(video, new bool[64], new double[64], 8, 8,
                null, null, 640.0, 400, results), Is.EqualTo(0));
            Assert.That(results, Is.Empty);
        }

        [Test]
        public void WrapPositive_PositiveModulo()
        {
            Assert.That(RadarPpiMath.WrapPositive(0.0), Is.EqualTo(0.0).Within(Tolerance));
            Assert.That(RadarPpiMath.WrapPositive(-0.5), Is.EqualTo(2.0 * Math.PI - 0.5).Within(Tolerance));
            Assert.That(RadarPpiMath.WrapPositive(3.0 * Math.PI), Is.EqualTo(Math.PI).Within(Tolerance));
            Assert.That(RadarPpiMath.WrapPositive(2.0 * Math.PI), Is.EqualTo(0.0).Within(Tolerance));
            Assert.That(RadarPpiMath.WrapPositive(-2.0 * Math.PI), Is.EqualTo(0.0).Within(Tolerance));
        }
    }
}
