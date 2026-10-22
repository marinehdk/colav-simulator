using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// RadarSurfaceOverlay 纯函数面测试（00-REPORT §4-1，任务书④：raster bin→世界
    /// 坐标投影 + 圈龄衰减）。组件本体在 Assembly-CSharp（材质/订阅 glue 不进测试，
    /// M2-E2 RadarOverlay/RadarMath 同分界）；数学全在 Sango.Vessels 的
    /// RadarOverlayMath（本 asmdef 直引）。三向锚点：投影 = RadarSpokeDecoder.
    /// ProjectBinToNe + TwinAnchor.ToLocal（P0 已各测，此处钉组合与 y 抬升/行源
    /// 语义）；像素映射 = web radar-video.js raster()（RGB 0.2/1.0/0.5×v、行龄门
    /// 1.1×scan_period）；圈龄衰减 = 任务书①"按圈龄衰减透明度"。
    /// </summary>
    public class RadarSurfaceOverlayTests
    {
        // live 锚定样例（TwinAnchor.FromShip 首帧本船 + M6TwinGeo.LandingM=(21000,-5000)）
        static TwinAnchor SampleAnchor() => new TwinAnchor
        {
            EastM = 1000.0,
            NorthM = 5000.0,
            LandingM = new Vector2(21000f, -5000f),
        };

        const float Tolerance = 1e-4f;

        [Test]
        public void RevolutionAlpha_DecaysByRevolutionAge()
        {
            Assert.That(RadarOverlayMath.RevolutionAlpha(0), Is.EqualTo(1f).Within(Tolerance), "最新圈全亮");
            Assert.That(RadarOverlayMath.RevolutionAlpha(1), Is.EqualTo(0.45f).Within(Tolerance), "上一圈余辉基线");
            Assert.That(RadarOverlayMath.RevolutionAlpha(2), Is.EqualTo(0f).Within(Tolerance), "环形容量 2 之外无残像");
            Assert.That(RadarOverlayMath.RevolutionAlpha(7), Is.EqualTo(0f).Within(Tolerance));
            Assert.That(RadarOverlayMath.RevolutionAlpha(-1), Is.EqualTo(1f).Within(Tolerance), "负龄（时钟未对齐）不惩罚");
        }

        [Test]
        public void RasterPixel_MirrorsWebVideoRasterMapping()
        {
            // radar-video.js raster()：image = (v*0.2, v, v*0.5)；此处 alpha=v（黑=透明）。
            var peak = RadarOverlayMath.RasterPixel(255);
            Assert.That(peak.r, Is.EqualTo(51));   // 255*0.2
            Assert.That(peak.g, Is.EqualTo(255));
            Assert.That(peak.b, Is.EqualTo(127));  // 255*0.5（截断）
            Assert.That(peak.a, Is.EqualTo(255), "强回波不透明");

            var floor = RadarOverlayMath.RasterPixel(0);
            Assert.That(floor.r, Is.EqualTo(0)); Assert.That(floor.g, Is.EqualTo(0));
            Assert.That(floor.b, Is.EqualTo(0)); Assert.That(floor.a, Is.EqualTo(0), "无回波全透明");

            var mid = RadarOverlayMath.RasterPixel(128);
            Assert.That(mid.r, Is.EqualTo(25));    // 128*0.2=25.6 截断（钉死字节，防映射漂移）
            Assert.That(mid.g, Is.EqualTo(128));
            Assert.That(mid.b, Is.EqualTo(64));
            Assert.That(mid.a, Is.EqualTo(128), "alpha=强度（半透明绿斑=海杂波）");

            Assert.That(RadarOverlayMath.RasterIntensity(255), Is.EqualTo(1f).Within(Tolerance));
            Assert.That(RadarOverlayMath.RasterIntensity(0), Is.EqualTo(0f).Within(Tolerance));
        }

        [Test]
        public void RowFresh_MirrorsWebAgeGate()
        {
            Assert.That(RadarOverlayMath.RowFresh(0.0, 2.6, 2.5), Is.True, "age 2.6s ≤ 1.1×2.5s");
            Assert.That(RadarOverlayMath.RowFresh(0.0, 2.8, 2.5), Is.False, "age 2.8s > 2.75s 剔除");
            Assert.That(RadarOverlayMath.RowFresh(3.0, 2.5, 2.5), Is.True, "未来行（时钟相位）按 age=0 放行（web max(0,·) 同式）");
            Assert.That(RadarOverlayMath.RowFresh(0.0, 100.0, 0.0), Is.True, "无描述子周期 = 降级恒新鲜");
        }

        [Test]
        public void BearingRow_WrapsLikeWebRasterRowLookup()
        {
            Assert.That(RadarOverlayMath.BearingRow(0.0, 2048), Is.EqualTo(0));
            Assert.That(RadarOverlayMath.BearingRow(Mathf.PI, 2048), Is.EqualTo(1024), "半转 = 行 1024");
            Assert.That(RadarOverlayMath.BearingRow(Mathf.PI / 2, 2048), Is.EqualTo(512));
            Assert.That(RadarOverlayMath.BearingRow(2.0 * Mathf.PI, 2048), Is.EqualTo(0), "整转回卷行 0");
            Assert.That(RadarOverlayMath.BearingRow(-0.0001, 2048), Is.EqualTo(2047), "负方位取正模到末行");
            Assert.That(RadarOverlayMath.BearingRow(3.0 * Mathf.PI, 2048), Is.EqualTo(1024), "多转取分数相位");
            Assert.That(RadarOverlayMath.BearingRow(1.0, 0), Is.EqualTo(0), "退化 spokes=0 护栏");
        }

        [Test]
        public void DiscVertexWorld_ProjectsRasterBinThroughRowOriginAndAnchor()
        {
            // 任务书④-1：raster bin → 世界坐标（行源 NE + 方位/距离 → 锚定场景，y=+0.5 贴水面）。
            TwinAnchor anchor = SampleAnchor();

            // 行源=锚点本船位，正北 100 m：local = (east−1000+21000, north−5000−5000)。
            Vector3 north100 = RadarOverlayMath.DiscVertexWorld(anchor, 5000.0, 1000.0, 0.0, 100.0, 0.5f);
            Assert.That(north100.x, Is.EqualTo(21000f).Within(Tolerance), "east→x");
            Assert.That(north100.z, Is.EqualTo(-4900f).Within(Tolerance), "north→z（+100 过锚后落 −4900）");
            Assert.That(north100.y, Is.EqualTo(0.5f).Within(Tolerance), "贴水面抬升 y+0.5");

            // 正东 200 m（bearing 90° = +east）。
            Vector3 east200 = RadarOverlayMath.DiscVertexWorld(anchor, 5000.0, 1000.0, Mathf.PI / 2, 200.0, 0.5f);
            Assert.That(east200.x, Is.EqualTo(21200f).Within(Tolerance));
            Assert.That(east200.z, Is.EqualTo(-5000f).Within(Tolerance));

            // 行源语义（web raster() 逐行平移）：本船已北移 50/东移 10 时采的行，
            // 同方位同距离的 bin 落点随之平移——盘面按行平移不拖影。
            Vector3 movedOrigin = RadarOverlayMath.DiscVertexWorld(anchor, 5050.0, 1010.0, 0.0, 100.0, 0.5f);
            Assert.That(movedOrigin.x, Is.EqualTo(21010f).Within(Tolerance), "行源东移 10 m 逐位平移");
            Assert.That(movedOrigin.z, Is.EqualTo(-4850f).Within(Tolerance), "行源北移 50 m 逐位平移（对比上例 −4900）");

            // 组合钉：bin 中心距离（RadarSpokeDecoder.BinRangeM）+ 行方位（RowBearingRad）
            // → 与显式 bearing/range 数值同一落点（P0 纯函数与本投影无缝拼接）。
            double bearing = RadarSpokeDecoder.RowBearingRad(512, 2048);
            double range = RadarSpokeDecoder.BinRangeM(1023, 1024, 1388.9);
            Vector3 composed = RadarOverlayMath.DiscVertexWorld(anchor, 5000.0, 1000.0, bearing, range, 0.5f);
            Vector3 direct = RadarOverlayMath.DiscVertexWorld(anchor, 5000.0, 1000.0, Mathf.PI / 2, range, 0.5f);
            Assert.That(composed.x, Is.EqualTo(direct.x).Within(1e-3f));
            Assert.That(composed.z, Is.EqualTo(direct.z).Within(1e-3f));
        }
    }
}
