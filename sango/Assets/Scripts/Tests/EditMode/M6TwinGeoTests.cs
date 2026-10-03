using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P3-12 孪生场景地理配准测试（spec #91）：M6TwinGeo 登记常量一致性 +
    /// geo_fit 覆盖度判定（消费烘焙掩膜 M6WaterMask，纯函数）。
    /// 掩膜真值锚点（tools/m6_water_mask.py 同源 DEM 实采）：
    ///   场景 (0,0) = 区域中心陆域（批 1 缺陷面，elev +41.3 m）；
    ///   主角泊位 (−1500,−5000) 水面（构建期 depth gate provenance）；
    ///   登记落点 (17000,−4800) 水面（海峡东侧开阔水域，DEM −12.8..−83 m）。
    /// </summary>
    public class M6TwinGeoTests
    {
        [Test]
        public void Landing_IsDocumentedEastOpenWater()
        {
            // 登记常量冻结（provenance 见 M6TwinGeo 类注）；改值必须重跑落点门。
            // x ≥ +18 km：落点须在激活远景环 tile 上（首版 (17000,−4800) 踩隐藏 tile 的教训）。
            Assert.That(M6TwinGeo.LandingM, Is.EqualTo(new Vector2(21000f, -5000f)));
            Assert.That(M6TwinGeo.LandingM.x, Is.GreaterThanOrEqualTo(18000f), "落点在激活地形 tile 带上");
            Assert.That(M6WaterMask.Sample(M6TwinGeo.LandingM.x, M6TwinGeo.LandingM.y),
                Is.EqualTo(M6WaterMask.Water), "登记落点在水面");
        }

        [Test]
        public void WaterMask_KnownPointsMatchDemTruth()
        {
            Assert.That(M6WaterMask.Sample(0f, 0f), Is.EqualTo(M6WaterMask.Land),
                "场景 (0,0) = 区域中心陆域（批 1 目标船压陆地贴图缺陷面）");
            Assert.That(M6WaterMask.Sample(-1500f, -5000f), Is.EqualTo(M6WaterMask.Water),
                "主角泊位水面（构建期 depth gate 同点）");
            Assert.That(M6WaterMask.Sample(35000f, 35000f), Is.EqualTo(M6WaterMask.Outside),
                "DEM 覆盖外");
        }

        [Test]
        public void ClassifyFit_LiveSessionBoxAtLanding_IsInside()
        {
            // live 语义（首帧本船锚）：7×7 km 会话框围绕落点（±3.5 km）——DEM 实采 water=1.000。
            var report = M6TwinGeo.ClassifyFit(
                M6TwinGeo.LandingM + new Vector2(-3500f, -3500f),
                M6TwinGeo.LandingM + new Vector2(3500f, 3500f));
            Assert.That(report.Fit, Is.EqualTo(M6TwinGeo.FitInside));
            Assert.That(report.WaterFraction, Is.GreaterThanOrEqualTo(0.98f));
            Assert.That(report.TerrainFraction, Is.EqualTo(1f).Within(1e-3f));
        }

        [Test]
        public void ClassifyFit_ReplayEncBoxAtLanding_IsInside()
        {
            // replay 语义（ENC origin 锚）：会话框 [落点, 落点+7 km]²——DEM 实采 water=1.000。
            var report = M6TwinGeo.ClassifyFit(
                M6TwinGeo.LandingM,
                M6TwinGeo.LandingM + new Vector2(7000f, 7000f));
            Assert.That(report.Fit, Is.EqualTo(M6TwinGeo.FitInside));
            Assert.That(report.WaterFraction, Is.GreaterThanOrEqualTo(0.98f));
        }

        [Test]
        public void ClassifyFit_Batch1LandingAtSceneOrigin_IsPartial()
        {
            // 批 1 缺陷面（回归哨兵）：原语义把会话框投到场景 (0,0) = 区域中心陆域
            // （DEM 实采 6×6 km 框 water≈0.153）——geo_fit 必须报 partial 而非 inside。
            var report = M6TwinGeo.ClassifyFit(new Vector2(-3000f, -3000f), new Vector2(3000f, 3000f));
            Assert.That(report.Fit, Is.EqualTo(M6TwinGeo.FitPartial), "陆域混入必须不判 inside");
            Assert.That(report.WaterFraction, Is.LessThan(0.5f));
        }

        [Test]
        public void ClassifyFit_BeyondDemCoverage_IsOutside()
        {
            var report = M6TwinGeo.ClassifyFit(
                new Vector2(M6WaterMask.ExtentM + 1000f, -5000f),
                new Vector2(M6WaterMask.ExtentM + 8000f, 2000f));
            Assert.That(report.Fit, Is.EqualTo(M6TwinGeo.FitOutside));
            Assert.That(report.TerrainFraction, Is.EqualTo(0f).Within(1e-3f));
        }

        [Test]
        public void ClassifyFit_MixedBoxSpanningCoast_IsPartial()
        {
            // 新加坡本岛南岸横跨框：北陆南水 → partial。
            var report = M6TwinGeo.ClassifyFit(new Vector2(15000f, -1000f), new Vector2(22000f, 6000f));
            Assert.That(report.Fit, Is.EqualTo(M6TwinGeo.FitPartial));
        }

        [Test]
        public void ClassifyFit_ZeroAreaBox_SamplesSingleCell()
        {
            // 首帧单点退化（0 面积）：按单格采样判水。
            var report = M6TwinGeo.ClassifyFit(M6TwinGeo.LandingM, M6TwinGeo.LandingM);
            Assert.That(report.Fit, Is.EqualTo(M6TwinGeo.FitInside));
            Assert.That(report.WaterFraction, Is.EqualTo(1f).Within(1e-3f));
        }

        [Test]
        public void FitVocabulary_IsContractSet()
        {
            // twin-bridge-v1 §3/§8 词汇面（§8 台账行同步冻结）。
            Assert.That(new[] { M6TwinGeo.FitInside, M6TwinGeo.FitPartial, M6TwinGeo.FitOutside },
                Is.EqualTo(new[] { "inside", "partial", "outside" }));
        }
    }
}
