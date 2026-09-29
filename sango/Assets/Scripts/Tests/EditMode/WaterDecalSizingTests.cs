using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M5 编目驱动水面 decal 尺寸表测试（water-decal-spike-notes §7.1 正式化项 1）。
    /// 钉死约定：12 m 档逐位复现 M4 spike 提交值（bow 12×12 / wake 14×28 / amp 0.4 / region 64，
    /// M4 验收不回退）；hero 档（42 m FCB）与长船档在区域预算内单调放大、幅度钳 [0.4, 0.8]；
    /// 两块 decal 的世界包围（艏波中心 +loa/2−0.4·bow.y，尾迹中心 −0.4·wake.y，各 ±size/2）
    /// 对 hero 量级（12–100 m）必须罩在 decalRegionSize 半边内。
    /// </summary>
    public class WaterDecalSizingTests
    {
        [Test]
        public void ForLoa_12m_ReproducesM4SpikeCommitValues()
        {
            var s = WaterDecalSizing.ForLoa(12f);
            Assert.That(s.bowRegionSize, Is.EqualTo(new Vector2(12f, 12f)));
            Assert.That(s.wakeRegionSize, Is.EqualTo(new Vector2(14f, 28f)));
            Assert.That(s.bowAmplitudeM, Is.EqualTo(0.4f).Within(0.0001f));
            Assert.That(s.decalRegionSize, Is.EqualTo(new Vector2(64f, 64f)));
        }

        [Test]
        public void ForLoa_DecalsFitInsideRegion_ForHeroRange()
        {
            foreach (float loa in new[] { 12f, 25f, 32f, 42f, 55f, 100f })
            {
                var s = WaterDecalSizing.ForLoa(loa);
                float half = s.decalRegionSize.x * 0.5f;
                float bowMin = (loa * 0.5f - 0.4f * s.bowRegionSize.y) - s.bowRegionSize.y * 0.5f;
                float bowMax = (loa * 0.5f - 0.4f * s.bowRegionSize.y) + s.bowRegionSize.y * 0.5f;
                Assert.That(bowMin, Is.GreaterThanOrEqualTo(-half), $"loa {loa}: bow decal exceeds region fore/aft");
                Assert.That(bowMax, Is.LessThanOrEqualTo(half), $"loa {loa}: bow decal exceeds region fore/aft");
                float wakeMin = (-0.4f * s.wakeRegionSize.y) - s.wakeRegionSize.y * 0.5f;
                float wakeMax = (-0.4f * s.wakeRegionSize.y) + s.wakeRegionSize.y * 0.5f;
                // 0.01 m 容差：wakeY=region/1.8 的钳位在浮点下可能差一个 ulp（100 m 档正好贴边）
                Assert.That(wakeMin, Is.GreaterThanOrEqualTo(-half - 0.01f), $"loa {loa}: wake decal exceeds region (stern)");
                Assert.That(wakeMax, Is.LessThanOrEqualTo(half), $"loa {loa}: wake decal exceeds region (bow)");
            }
        }

        [Test]
        public void ForLoa_Amplitude_ClampedAndMonotone()
        {
            float prev = -1f;
            for (float loa = 6f; loa <= 400f; loa += 2f)
            {
                float amp = WaterDecalSizing.ForLoa(loa).bowAmplitudeM;
                Assert.That(amp, Is.InRange(0.4f, 0.8f));
                Assert.That(amp, Is.GreaterThanOrEqualTo(prev - 1e-4f));
                prev = amp;
            }
            Assert.That(WaterDecalSizing.ForLoa(300f).bowAmplitudeM, Is.EqualTo(0.8f).Within(0.0001f));
        }

        [Test]
        public void ForLoa_42mFcbHero_ScalesUpFrom12mBaseline()
        {
            // hero 换档 sanity：42 m 档比 12 m 档大、且幅度按 √(42/12)×0.4≈0.748
            var s = WaterDecalSizing.ForLoa(42f);
            var b = WaterDecalSizing.ForLoa(12f);
            Assert.That(s.bowRegionSize.x, Is.GreaterThan(b.bowRegionSize.x));
            Assert.That(s.wakeRegionSize.y, Is.GreaterThan(b.wakeRegionSize.y));
            Assert.That(s.bowAmplitudeM, Is.EqualTo(0.4f * Mathf.Sqrt(42f / 12f)).Within(0.001f));
        }

        [Test]
        public void ForLoa_DegenerateLoa_ClampedToSanityFloor()
        {
            var s = WaterDecalSizing.ForLoa(0.1f); // 编目缺档兜底路径不该产生 0 尺寸
            Assert.That(s.bowRegionSize.x, Is.GreaterThanOrEqualTo(12f));
            Assert.That(s.wakeRegionSize.y, Is.GreaterThanOrEqualTo(28f));
            Assert.That(s.decalRegionSize.x, Is.EqualTo(64f));
        }
    }
}
