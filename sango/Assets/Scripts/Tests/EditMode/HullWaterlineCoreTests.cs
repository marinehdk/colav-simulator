using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M4-B 水线纯核心 EditMode 测试（issue #87 批次 B 项 1/4）：HullWaterlineCore 两函数，
    /// 合成数据 worked examples（先例 NavigationLightsCoreTests：期望值全部手算，不回声实现）。
    /// 钉死约定：偏移 = waterHeight − baseline 钳 [−draft, +freeboard]（米，正=湿带沿干舷上爬）；
    /// boot top 带高 = 请求值钳 [0, freeboard]。
    /// </summary>
    public class HullWaterlineCoreTests
    {
        const float k_Tol = 1e-5f;

        [Test]
        public void WetBand_ZeroExcursion_ZeroOffset()
        {
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(0f, 0f, 1f, 2f), Is.EqualTo(0f).Within(k_Tol),
                "静水（水面=设计水线）湿带上界就在设计水线");
        }

        [Test]
        public void WetBand_RisePassesThrough_UntilFreeboardClamp()
        {
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(0.3f, 0f, 1f, 2f), Is.EqualTo(0.3f).Within(k_Tol),
                "水面升 0.3 m（< 干舷 2 m）原样传导");
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(2f, 0f, 1f, 2f), Is.EqualTo(2f).Within(k_Tol),
                "恰到干舷上界");
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(5f, 0f, 1f, 2f), Is.EqualTo(2f).Within(k_Tol),
                "水面升过甲板（异常波）钳在干舷 = 湿带不脱离船体");
        }

        [Test]
        public void WetBand_FallClampsAtDraft()
        {
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(-0.4f, 0f, 1f, 2f), Is.EqualTo(-0.4f).Within(k_Tol),
                "水面退 0.4 m（< 吃水 1 m）原样传导");
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(-5f, 0f, 1f, 2f), Is.EqualTo(-1f).Within(k_Tol),
                "水面退过龙骨钳在 -draft");
        }

        [Test]
        public void WetBand_NonZeroBaseline_SubtractsFirst()
        {
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(0.2f, 0.1f, 1f, 2f), Is.EqualTo(0.1f).Within(k_Tol),
                "偏移 = water − baseline（基线非 0 时先减）");
        }

        [Test]
        public void WetBand_DegenerateRanges_PinToZero()
        {
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(-0.4f, 0f, -1f, 2f), Is.EqualTo(0f).Within(k_Tol),
                "负吃水（非法）视 0：向下不可动");
            Assert.That(HullWaterlineCore.WetBandUpperOffsetM(0.4f, 0f, 1f, -2f), Is.EqualTo(0f).Within(k_Tol),
                "负干舷（非法）视 0：向上不可动");
        }

        [Test]
        public void BootTop_PassesRequested_ClampsToFreeboard()
        {
            Assert.That(HullWaterlineCore.BootTopBandHeightM(0.8f, 1.5f), Is.EqualTo(0.8f).Within(k_Tol),
                "请求 0.8 < 干舷 1.5 原样");
            Assert.That(HullWaterlineCore.BootTopBandHeightM(2.0f, 1.5f), Is.EqualTo(1.5f).Within(k_Tol),
                "请求超过型深钳干舷");
            Assert.That(HullWaterlineCore.BootTopBandHeightM(-1f, 1.5f), Is.EqualTo(0f).Within(k_Tol),
                "负请求 = 不铺带");
        }

        [Test]
        public void BootTop_NonPositiveFreeboard_NoBand()
        {
            Assert.That(HullWaterlineCore.BootTopBandHeightM(0.8f, 0f), Is.EqualTo(0f), "干舷 0（水面=盒顶，退化）不铺");
            Assert.That(HullWaterlineCore.BootTopBandHeightM(0.8f, -0.5f), Is.EqualTo(0f), "负干舷（非法）不铺");
        }
    }
}
