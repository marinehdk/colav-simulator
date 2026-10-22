using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// RadarTargetMarkers 纯函数面测试（00-REPORT §4-2，任务书②）。组件本体在
    /// Assembly-CSharp（壳/标签 glue 不进测试）；数学与 DTO 在 RadarOverlayMath/
    /// RadarDisplayReturn（Sango.Vessels 直引）。锚点：display_returns 单条形状 =
    /// 后端 RadarScanPacket.to_dict（radar_scan.py:38-50，confidence=PD、绝对 NE，
    /// 协方差嵌套数组 JsonUtility 静默跳过）；匹配语义 = 只标记检测目标（无标记
    /// 即未检测——探测边界可读），匹配半径外不脑补。
    /// </summary>
    public class RadarTargetMarkersTests
    {
        static TwinAnchor SampleAnchor() => new TwinAnchor
        {
            EastM = 1000.0,
            NorthM = 5000.0,
            LandingM = new Vector2(21000f, -5000f),
        };

        const float Tolerance = 1e-4f;

        [Test]
        public void ReturnWorldPosition_ProjectsAbsoluteNeThroughAnchor()
        {
            Vector3 world = RadarOverlayMath.ReturnWorldPosition(SampleAnchor(), 5100.0, 1200.0, 0.6f);
            Assert.That(world.x, Is.EqualTo(21200f).Within(Tolerance), "east 1200 → 锚定局部 200 → +landing");
            Assert.That(world.z, Is.EqualTo(-4900f).Within(Tolerance), "north 5100 → 局部 100 − 5000");
            Assert.That(world.y, Is.EqualTo(0.6f).Within(Tolerance));
        }

        [Test]
        public void NearestVesselIndex_MatchesWithinRadiusOnly()
        {
            var vessels = new[] { new Vector2(100f, 200f), new Vector2(500f, 200f) };
            Assert.That(RadarOverlayMath.NearestVesselIndex(new Vector2(110f, 205f), vessels, 50f), Is.EqualTo(0), "近者胜");
            Assert.That(RadarOverlayMath.NearestVesselIndex(new Vector2(400f, 200f), vessels, 50f), Is.EqualTo(-1),
                "最近 100 m 仍超 50 m 门 = 不匹配（未检测船不脑补壳）");
            Assert.That(RadarOverlayMath.NearestVesselIndex(new Vector2(400f, 200f), vessels, 150f), Is.EqualTo(1),
                "放宽到 150 m 匹配东船");
            Assert.That(RadarOverlayMath.NearestVesselIndex(new Vector2(0f, 0f), new Vector2[0], 100f), Is.EqualTo(-1), "空船表");
            Assert.That(RadarOverlayMath.NearestVesselIndex(new Vector2(0f, 0f), null, 100f), Is.EqualTo(-1), "null 船表");
        }

        [Test]
        public void MarkerLabelText_RangeAndConfidence()
        {
            Assert.That(RadarOverlayMath.MarkerLabelText(0.873f, 213.4f), Is.EqualTo("RDR 87% 213m"));
            Assert.That(RadarOverlayMath.MarkerLabelText(1.0f, 54f), Is.EqualTo("RDR 100% 54m"));
            Assert.That(RadarOverlayMath.MarkerLabelText(0.04f, 1388.9f), Is.EqualTo("RDR 4% 1389m"), "四舍五入非截断（{0:0} 档）");
        }

        [Test]
        public void DisplayReturnDocument_ParsesBackendScanSubset()
        {
            // radar_scans[*] 子集形状（RadarScanPacket.to_dict 键面）：display_returns
            // + 本测试不消费的兄弟键（returns/descriptor/…）静默跳过。
            const string json = "{\"sensor_label\":\"radar_x\",\"t_s\":2.5," +
                "\"display_returns\":[" +
                "{\"north_m\":6957600.5,\"east_m\":39600.25,\"t_s\":2.4,\"snr_db\":12.5,\"confidence\":0.87," +
                "\"covariance_ne_m2\":[[4.0,0.0],[0.0,4.0]]}," +
                "{\"north_m\":6958000.0,\"east_m\":39000.0,\"t_s\":1.2,\"snr_db\":3.1,\"confidence\":0.31}]," +
                "\"returns\":[]}";
            var document = JsonUtility.FromJson<RadarDisplayScanDocument>(json);
            Assert.That(document, Is.Not.Null);
            Assert.That(document.display_returns.Length, Is.EqualTo(2));
            Assert.That(document.display_returns[0].north_m, Is.EqualTo(6957600.5).Within(1e-9));
            Assert.That(document.display_returns[0].east_m, Is.EqualTo(39600.25).Within(1e-9));
            Assert.That(document.display_returns[0].t_s, Is.EqualTo(2.4).Within(1e-9));
            Assert.That(document.display_returns[0].snr_db, Is.EqualTo(12.5).Within(1e-9));
            Assert.That(document.display_returns[0].confidence, Is.EqualTo(0.87f).Within(1e-6), "confidence=PD");
            Assert.That(document.display_returns[1].confidence, Is.EqualTo(0.31f).Within(1e-6));

            // 缺键/空窗（后端无检测滑窗时 display_returns=[]）。
            Assert.That(JsonUtility.FromJson<RadarDisplayScanDocument>("{\"t_s\":2.5}").display_returns, Is.Null);
            var empty = JsonUtility.FromJson<RadarDisplayScanDocument>("{\"display_returns\":[]}");
            Assert.That(empty.display_returns.Length, Is.EqualTo(0), "空滑窗合法（本转无检测）");
        }
    }
}
