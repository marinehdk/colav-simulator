using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-E2 雷达几何缝 EditMode 测试（spec #85 Testing Decisions）：blip 在/出量程、
    /// 方位/距离 worked examples。钉死约定：东 = +x，北 = +z；方位角自北顺时针
    /// （spec 明示 north = 0°、east = 90°）；雷达盘北向上（归一化 blip：右 = 东、上 = 北）。
    /// 期望值来自独立几何事实（罗盘方位、3-4-5 三角形），不回声实现里的 atan2 公式。
    /// </summary>
    public class RadarMathTests
    {
        const float k_AngleTolDeg = 0.01f;
        const float k_PosTol = 1e-4f;
        static readonly Vector2 k_Origin = new Vector2(14f, -6f); // M1 demo 船泊位（任意非原点）

        // ── 方位角 worked examples（罗盘事实）───────────────────────────────────────
        [Test]
        public void Bearing_NorthIsZero_EastIsNinety()
        {
            Assert.That(RadarMath.BearingDeg(k_Origin, k_Origin + new Vector2(0f, 100f)),
                Is.EqualTo(0f).Within(k_AngleTolDeg), "正北 = 0°（spec）");
            Assert.That(RadarMath.BearingDeg(k_Origin, k_Origin + new Vector2(100f, 0f)),
                Is.EqualTo(90f).Within(k_AngleTolDeg), "正东 = 90°（spec）");
        }

        [Test]
        public void Bearing_SouthIs180_WestIs270()
        {
            Assert.That(RadarMath.BearingDeg(k_Origin, k_Origin + new Vector2(0f, -100f)),
                Is.EqualTo(180f).Within(k_AngleTolDeg), "正南 = 180°");
            Assert.That(RadarMath.BearingDeg(k_Origin, k_Origin + new Vector2(-100f, 0f)),
                Is.EqualTo(270f).Within(k_AngleTolDeg), "正西 = 270°");
        }

        [Test]
        public void Bearing_NortheastIs45_WrapsBelow360()
        {
            Assert.That(RadarMath.BearingDeg(k_Origin, k_Origin + new Vector2(100f, 100f)),
                Is.EqualTo(45f).Within(k_AngleTolDeg), "东北等距 = 45°");
            Assert.That(RadarMath.BearingDeg(k_Origin, k_Origin + new Vector2(-1f, 0.01f)),
                Is.GreaterThan(180f).And.LessThan(360f), "结果恒落在 [0, 360) 半开区间");
        }

        // ── 距离（3-4-5 三角形）──────────────────────────────────────────────────────
        [Test]
        public void Range_ThreeFourTriangle_IsFive()
        {
            Assert.That(RadarMath.RangeM(k_Origin, k_Origin + new Vector2(30f, 40f)),
                Is.EqualTo(50f).Within(1e-3f), "3-4-5 三角：30/40 → 50 m");
        }

        // ── 量程判定：边界含 ─────────────────────────────────────────────────────────
        [Test]
        public void InRange_AtExactlyRange_True_OutsideRange_False()
        {
            Assert.That(RadarMath.InRange(k_Origin, k_Origin + new Vector2(0f, 600f), 600f),
                Is.True, "恰在量程上 = 在内（边界含）");
            Assert.That(RadarMath.InRange(k_Origin, k_Origin + new Vector2(0f, 601f), 600f),
                Is.False, "出量程 1 m = 在外（blip 隐藏）");
            Assert.That(RadarMath.InRange(k_Origin, k_Origin + new Vector2(0f, 100f), 600f),
                Is.True, "量程内近距离 = 在内");
        }

        // ── 归一化 blip：右 = 东、上 = 北、模长 = 距离/量程 ──────────────────────────
        [Test]
        public void BlipNormalized_EastAtHalfRange_RightHalf()
        {
            var b = RadarMath.BlipNormalized(k_Origin, k_Origin + new Vector2(300f, 0f), 600f);
            Assert.That(b.x, Is.EqualTo(0.5f).Within(k_PosTol), "正东半量程 → 屏右半幅");
            Assert.That(b.y, Is.EqualTo(0f).Within(k_PosTol), "正东无北向分量");
        }

        [Test]
        public void BlipNormalized_NorthAtFullRange_TopEdge()
        {
            var b = RadarMath.BlipNormalized(k_Origin, k_Origin + new Vector2(0f, 600f), 600f);
            Assert.That(b.x, Is.EqualTo(0f).Within(k_PosTol));
            Assert.That(b.y, Is.EqualTo(1f).Within(k_PosTol), "正北全量程 → 盘顶缘");
        }

        [Test]
        public void BlipNormalized_OutsideRange_ExceedsUnitDisc()
        {
            var b = RadarMath.BlipNormalized(k_Origin, k_Origin + new Vector2(0f, 900f), 600f);
            Assert.That(b.magnitude, Is.GreaterThan(1f), "出量程目标 blip 模长 > 1（配合 InRange 隐藏）");
        }
    }
}
