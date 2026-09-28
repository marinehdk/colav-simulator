using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M4-B COLREG 光弧纯核心 EditMode 测试（issue #87 批次 B 项 3）：NavigationLightsCore.
    /// SectorIntensity / GetArc worked examples。约定钉死：relBearing 0=正艏、顺时针（右舷）
    /// 为正 [0,360)；弧内（含边界）1、弧外 0、边界外 falloffDeg 内线性衰减（Annex I §9
    /// 1-3° 过渡带，默认 3°）；跨 0/360 环绕。手算锚值：falloff 3° 时边界外 1° → 2/3、
    /// 1.5° → 0.5、2° → 1/3、2.5° → 1/6、3° → 0。
    /// </summary>
    public class NavigationLightsSectorTests
    {
        const float k_Tol = 1e-4f;
        const float k_Falloff = 3f;

        // ── 右舷舷灯（Rule 21：0→112.5，自艏向艉 22.5° 后起算）─────────────────
        [Test]
        public void StarboardSidelight_InsideArc_One_IncludingBoundaries()
        {
            Assert.That(NavigationLightsCore.SectorIntensity(30f, 0f, 112.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "右舷前侧 30° 满强度");
            Assert.That(NavigationLightsCore.SectorIntensity(0f, 0f, 112.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "正艏 = 弧起点（含边界）");
            Assert.That(NavigationLightsCore.SectorIntensity(112.5f, 0f, 112.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "弧终点 112.5°（含边界）");
        }

        [Test]
        public void StarboardSidelight_FarOutside_Zero()
        {
            Assert.That(NavigationLightsCore.SectorIntensity(180f, 0f, 112.5f, k_Falloff), Is.EqualTo(0f), "正艉方向右舷灯灭");
            Assert.That(NavigationLightsCore.SectorIntensity(130f, 0f, 112.5f, k_Falloff), Is.EqualTo(0f), "过界 17.5° ≫ falloff");
        }

        [Test]
        public void StarboardSidelight_FalloffBand_DecreasesMonotonically()
        {
            float prev = 1.5f;
            for (float over = 0f; over <= 3f; over += 0.5f)
            {
                float f = NavigationLightsCore.SectorIntensity(112.5f + over, 0f, 112.5f, k_Falloff);
                Assert.That(f, Is.LessThanOrEqualTo(prev + k_Tol), $"过界 {over}° 强度须单调不增");
                prev = f;
            }
            Assert.That(NavigationLightsCore.SectorIntensity(114f, 0f, 112.5f, k_Falloff), Is.EqualTo(0.5f).Within(k_Tol), "过界 1.5° → 1−1.5/3 = 0.5");
            Assert.That(NavigationLightsCore.SectorIntensity(115.5f, 0f, 112.5f, k_Falloff), Is.EqualTo(0f).Within(k_Tol), "过界 3° = 实际截止");
        }

        [Test]
        public void StarboardSidelight_BeforeStartEdge_DecaysAcross360Wrap()
        {
            // 起始边界 0° 的另一侧 = 357..360：358 距起点 2° → 1/3。
            Assert.That(NavigationLightsCore.SectorIntensity(358f, 0f, 112.5f, k_Falloff), Is.EqualTo(1f / 3f).Within(k_Tol), "跨 0 环绕：358° 距起始边界 2°");
            Assert.That(NavigationLightsCore.SectorIntensity(355f, 0f, 112.5f, k_Falloff), Is.EqualTo(0f), "355° 距起点 5° 已截止");
        }

        // ── 左舷舷灯（247.5→360，跨 0 环绕）──────────────────────────────────
        [Test]
        public void PortSidelight_ArcSpans247To360_WrapsToBow()
        {
            Assert.That(NavigationLightsCore.SectorIntensity(300f, 247.5f, 360f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "左舷后侧 300° 满强度");
            Assert.That(NavigationLightsCore.SectorIntensity(359f, 247.5f, 360f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "359° 仍在弧内");
            Assert.That(NavigationLightsCore.SectorIntensity(2f, 247.5f, 360f, k_Falloff), Is.EqualTo(1f / 3f).Within(k_Tol), "跨 0：2° 距 360 端 2° → 1/3");
            Assert.That(NavigationLightsCore.SectorIntensity(245f, 247.5f, 360f, k_Falloff), Is.EqualTo(1f / 6f).Within(k_Tol), "245° 越前边界 2.5° → 1/6");
            Assert.That(NavigationLightsCore.SectorIntensity(240f, 247.5f, 360f, k_Falloff), Is.EqualTo(0f), "240° 已截止");
        }

        // ── 桅灯（247.5→112.5，225° 跨 0/360 环绕：自艏向两舷各 112.5°）──────────
        [Test]
        public void Masthead_225Arc_WrapsAcrossZero()
        {
            Assert.That(NavigationLightsCore.SectorIntensity(0f, 247.5f, 112.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "正艏满强度");
            Assert.That(NavigationLightsCore.SectorIntensity(350f, 247.5f, 112.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "350°（跨 0 段）满强度");
            Assert.That(NavigationLightsCore.SectorIntensity(60f, 247.5f, 112.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "60° 满强度");
            Assert.That(NavigationLightsCore.SectorIntensity(180f, 247.5f, 112.5f, k_Falloff), Is.EqualTo(0f), "正艉 = 桅灯盲区中心");
            Assert.That(NavigationLightsCore.SectorIntensity(115f, 247.5f, 112.5f, k_Falloff), Is.EqualTo(1f / 6f).Within(k_Tol), "过艏侧端（112.5°）2.5° → 1/6");
            Assert.That(NavigationLightsCore.SectorIntensity(245f, 247.5f, 112.5f, k_Falloff), Is.EqualTo(1f / 6f).Within(k_Tol), "过艉侧端（247.5°）2.5° → 1/6（两端对称）");
        }

        // ── 艉灯（112.5→247.5，135°）───────────────────────────────────────
        [Test]
        public void SternLight_135Arc_CentredOnAstern()
        {
            Assert.That(NavigationLightsCore.SectorIntensity(180f, 112.5f, 247.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "正艉满强度");
            Assert.That(NavigationLightsCore.SectorIntensity(110f, 112.5f, 247.5f, k_Falloff), Is.EqualTo(1f / 6f).Within(k_Tol), "艏侧边界外 2.5° → 1/6");
            Assert.That(NavigationLightsCore.SectorIntensity(250f, 112.5f, 247.5f, k_Falloff), Is.EqualTo(1f / 6f).Within(k_Tol), "艉侧边界外 2.5° → 1/6");
            Assert.That(NavigationLightsCore.SectorIntensity(60f, 112.5f, 247.5f, k_Falloff), Is.EqualTo(0f), "艏侧远处灭");
            Assert.That(NavigationLightsCore.SectorIntensity(300f, 112.5f, 247.5f, k_Falloff), Is.EqualTo(0f), "舷侧远处灭");
        }

        // ── Rule 21 语义与鲁棒性 ────────────────────────────────────────────
        [Test]
        public void DeadAhead_BothSidelightsAtBoundaryIntensity()
        {
            // Rule 21：两舷灯弧在正艏相接——正艏方位上两灯均在各自弧端点 = 均可见。
            Assert.That(NavigationLightsCore.SectorIntensity(0f, 0f, 112.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "右舷灯在正艏可见");
            Assert.That(NavigationLightsCore.SectorIntensity(0f, 247.5f, 360f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "左舷灯在正艏可见");
        }

        [Test]
        public void ZeroFalloff_HardCutoffAtBoundary()
        {
            Assert.That(NavigationLightsCore.SectorIntensity(112.5f, 0f, 112.5f, 0f), Is.EqualTo(1f).Within(k_Tol), "边界仍在弧内");
            Assert.That(NavigationLightsCore.SectorIntensity(112.6f, 0f, 112.5f, 0f), Is.EqualTo(0f), "falloff=0 = 无过渡带硬截止");
        }

        [Test]
        public void BearingNormalization_NegativeAndMultiTurnInputs()
        {
            Assert.That(NavigationLightsCore.SectorIntensity(-30f, 0f, 112.5f, k_Falloff), Is.EqualTo(0f), "-30° ≡ 330°：右舷灯灭");
            Assert.That(NavigationLightsCore.SectorIntensity(-30f, 247.5f, 360f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "-30° ≡ 330°：左舷灯满强度");
            Assert.That(NavigationLightsCore.SectorIntensity(390f, 0f, 112.5f, k_Falloff), Is.EqualTo(1f).Within(k_Tol), "390° ≡ 30° 归一");
        }

        [Test]
        public void GetArc_SpansMatchRule21()
        {
            // 顺时针弧长 = (end − start + 360) mod 360：舷灯 112.5 / 桅灯 225 / 艉灯 135。
            Assert.That(SpanOf(LampKind.StarboardSidelight), Is.EqualTo(112.5f).Within(k_Tol), "舷灯 = 自艏向艉 22.5° 后起算的 112.5°");
            Assert.That(SpanOf(LampKind.PortSidelight), Is.EqualTo(112.5f).Within(k_Tol));
            Assert.That(SpanOf(LampKind.Masthead), Is.EqualTo(225f).Within(k_Tol), "桅灯 225°");
            Assert.That(SpanOf(LampKind.SternLight), Is.EqualTo(135f).Within(k_Tol), "艉灯 135°");
        }

        static float SpanOf(LampKind kind)
        {
            var (start, end) = NavigationLightsCore.GetArc(kind);
            return Mathf.Repeat(end - start, 360f);
        }
    }
}
