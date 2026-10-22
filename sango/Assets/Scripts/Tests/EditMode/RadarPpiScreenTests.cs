using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// RadarPpiScreen 数据面/开关面测试(00-REPORT §5/§6 P2)。组件在 Assembly-CSharp
    /// (Runtime 根无 asmdef),经 TestReflection 反射驱动(TwinBridgeClockGuardTests 先例);
    /// 纯静态(ResolveScaleM/OwnNeFromScene/ComputeRowDeltas)与 DTO(RadarSpokeFrame/
    /// RadarPpiDetection,Sango.Vessels)直接引用。EditMode 无 Awake——数据方法不触 UI。
    /// </summary>
    public class RadarPpiScreenTests
    {
        GameObject _go;
        Component _screen;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("radar-ppi-screen-under-test");
            _screen = _go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.RadarPpiScreen"));
        }

        [TearDown]
        public void TearDown()
        {
            if (_go != null) Object.DestroyImmediate(_go);
        }

        MethodInfo Method(string name) => _screen.GetType().GetMethod(name,
            BindingFlags.Public | BindingFlags.Instance);

        T Call<T>(string name, params object[] args) => (T)Method(name).Invoke(_screen, args);

        bool ScreenVisible => (bool)_screen.GetType().GetProperty("ScreenVisible").GetValue(_screen);

        int DetectionCount => ((IReadOnlyList<RadarPpiDetection>)_screen.GetType()
            .GetProperty("Detections").GetValue(_screen)).Count;

        /// <summary>合成帧:spokes×bins 平坦噪声 30 + row 500 bins 30/31 尖峰 200;
        /// 行源恒 (N=1000, E=2000)、行时间恒 1.0(采集完成域)。</summary>
        static RadarSpokeFrame SyntheticFrame(int spokes = 520, int bins = 64, double rangeM = 640.0)
        {
            var frame = new RadarSpokeFrame
            {
                spokes = spokes,
                bins = bins,
                rangeM = rangeM,
                tS = 1.0,
                raster = new byte[spokes * bins],
                rowTimesS = new double[spokes],
                rowBearingsRad = null, // 回退 row·2π/spokes(ClusterDetections 同回退)
                rowOriginsNeM = new double[spokes][],
            };
            for (int i = 0; i < frame.raster.Length; i++) frame.raster[i] = 30;
            frame.raster[500 * bins + 30] = 200;
            frame.raster[500 * bins + 31] = 200;
            for (int r = 0; r < spokes; r++)
            {
                frame.rowTimesS[r] = 1.0;
                frame.rowOriginsNeM[r] = new[] { 1000.0, 2000.0 };
            }
            return frame;
        }

        [Test]
        public void ApplyRadarView_VocabularyGatesScreenVisibility()
        {
            Assert.That(ScreenVisible, Is.False, "radar_view 默认 off → 屏隐藏");
            Call<object>("ApplyRadarView", "ppi");
            Assert.That(ScreenVisible, Is.True);
            Call<object>("ApplyRadarView", "off");
            Assert.That(ScreenVisible, Is.False);
            Call<object>("ApplyRadarView", "both");
            Assert.That(ScreenVisible, Is.True, "both = overlay+ppi 同开(效果面纯函数)");
            Call<object>("ApplyRadarView", "overlay");
            Assert.That(ScreenVisible, Is.False, "overlay 位不含 ppi");
            Call<object>("ApplyRadarView", "garbage");
            Assert.That(ScreenVisible, Is.False, "未知词汇效果面 = 双 false(词汇拒绝在 TwinBridge 层)");
        }

        [Test]
        public void TakeRevolutionAndCfarSlicing_ProducesExpectedDetection()
        {
            Call<object>("TakeRevolution", SyntheticFrame());
            Assert.That(DetectionCount, Is.EqualTo(0), "流水未完成不产检测");

            bool done = false;
            int steps = 0;
            while (!done && steps < 16)
            {
                done = Call<bool>("CfarSliceStep");
                steps++;
            }
            Assert.That(steps, Is.EqualTo(3), "520 行 / 每片 256 行 = 3 片完成(2 片不够)");
            Assert.That(done, Is.True);

            var detections = (IReadOnlyList<RadarPpiDetection>)_screen.GetType()
                .GetProperty("Detections").GetValue(_screen);
            Assert.That(detections.Count, Is.EqualTo(1), "单尖峰簇");
            Assert.That((int)_screen.GetType().GetProperty("CfarFoundClusters").GetValue(_screen),
                Is.EqualTo(1));

            var detection = detections[0];
            double bearing = RadarSpokeDecoder.RowBearingRad(500, 520);
            double expectedRange = 0.5 * (RadarSpokeDecoder.BinRangeM(30, 64, 640.0)
                                          + RadarSpokeDecoder.BinRangeM(31, 64, 640.0));
            Assert.That(detection.CellCount, Is.EqualTo(2));
            Assert.That(detection.NorthM, Is.EqualTo(1000.0 + System.Math.Cos(bearing) * expectedRange).Within(1e-6));
            Assert.That(detection.EastM, Is.EqualTo(2000.0 + System.Math.Sin(bearing) * expectedRange).Within(1e-6));
            Assert.That(detection.Intensity, Is.GreaterThan(0.08), "高 excess → 高亮度");

            // 新转到达:流水复位,重新分片
            Call<object>("TakeRevolution", SyntheticFrame());
            Assert.That(DetectionCount, Is.EqualTo(0), "新转清空检测(重新 CFAR)");
            Assert.That(Call<bool>("CfarSliceStep"), Is.False, "首片后未完(520 行)");
        }

        [Test]
        public void TakeRevolution_IgnoresMalformedFrames()
        {
            Call<object>("TakeRevolution", new object[] { null });
            Call<object>("TakeRevolution", new RadarSpokeFrame { spokes = 0, bins = 0 });
            Assert.That(Call<bool>("CfarSliceStep"), Is.True, "无帧恒完成(空流水)");
            Assert.That(DetectionCount, Is.EqualTo(0));
        }

        [Test]
        public void ResolveScaleM_FallbackChain()
        {
            // 帧 range_m(后端 active_range_m)→ 描述子 range_scale_nm×1852 → web 默认 6 nm
            System.Type screen = TestReflection.FindAssemblyCSharpType("Sango.RadarPpiScreen");
            var resolve = screen.GetMethod("ResolveScaleM", BindingFlags.Public | BindingFlags.Static);
            Assert.That((double)resolve.Invoke(null, new object[] { 640.0, null }), Is.EqualTo(640.0));
            Assert.That((double)resolve.Invoke(null, new object[] { 0.0, new RadarPpiDescriptor { range_scale_nm = 0.75 } }),
                Is.EqualTo(0.75 * RadarPpiMath.NmPerM).Within(1e-9));
            Assert.That((double)resolve.Invoke(null, new object[] { 0.0, null }),
                Is.EqualTo(6.0 * RadarPpiMath.NmPerM).Within(1e-9));
        }

        [Test]
        public void OwnNeFromScene_InverseOfTwinPoseScenePosition()
        {
            System.Type screen = TestReflection.FindAssemblyCSharpType("Sango.RadarPpiScreen");
            var own = screen.GetMethod("OwnNeFromScene", BindingFlags.Public | BindingFlags.Static);

            var anchor = new TwinAnchor { EastM = 39500.0, NorthM = 6957500.0, LandingM = M6TwinGeo.LandingM };
            var scenePos = new Vector3(1000f, 0f, 3000f);
            var args = new object[] { scenePos, anchor, null, null };
            own.Invoke(null, args);
            double north = (double)args[2], east = (double)args[3];

            // 逆变换正确性 = 正变换回环:TwinPose.ScenePosition(NE) == scenePos
            var ship = new ColavTelemetry.ShipEntry { east = east, north = north };
            Vector3 roundTrip = TwinPose.ScenePosition(ship, anchor);
            Assert.That(roundTrip.x, Is.EqualTo(scenePos.x).Within(0.001));
            Assert.That(roundTrip.z, Is.EqualTo(scenePos.z).Within(0.001));
        }

        [Test]
        public void ComputeRowDeltas_PacksNorthEastChannels_CpuDoubleDomain()
        {
            System.Type screen = TestReflection.FindAssemblyCSharpType("Sango.RadarPpiScreen");
            var deltas = screen.GetMethod("ComputeRowDeltas", BindingFlags.Public | BindingFlags.Static);

            // RGFloat 通道序:R = 北差(ownN−originN)、G = 东差(ownE−originE)——shader _RowDelta 同序
            var origins = new double[][] { new[] { 6957490.0, 39495.0 }, null };
            var buffer = new float[6]; // 3 行
            deltas.Invoke(null, new object[] { 6957500.0, 39500.0, origins, buffer });
            Assert.That(buffer[0], Is.EqualTo(10f).Within(1e-3), "R = 北差");
            Assert.That(buffer[1], Is.EqualTo(5f).Within(1e-3), "G = 东差");
            Assert.That(buffer[2], Is.EqualTo(0f));
            Assert.That(buffer[3], Is.EqualTo(0f), "行源缺行 → 0(时间门另弃)");
            Assert.That(buffer[4], Is.EqualTo(0f));
            Assert.That(buffer[5], Is.EqualTo(0f), "越行源表尾 → 0");

            // 大数减法在 CPU double 域:7e6 级坐标差保持米级精度
            buffer = new float[2];
            deltas.Invoke(null, new object[] { 6957500.0, 39500.0, new double[][] { new[] { 6957500.5, 39499.75 } }, buffer });
            Assert.That(buffer[0], Is.EqualTo(-0.5f).Within(1e-4), "亚米级差不被 float 大数吞位");
            Assert.That(buffer[1], Is.EqualTo(0.25f).Within(1e-4));
        }
    }
}
