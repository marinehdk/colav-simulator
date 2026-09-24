using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-E2 桥楼矢量箭头端点缝 EditMode 测试（spec #85 Testing Decisions）：
    /// 速度箭头长度 ∝ 速度（documented 比例因子 2 m/(m/s)，stub 保底）、
    /// 航点箭头指向活动航点方位（定长）。钉死约定（WaypointKinematicsTests 同源）：
    /// 东 = +x，北 = +z，艏向角自北顺时针，艏向单位向量 = (sin h, 0, cos h)。
    /// 期望值来自独立几何事实（罗盘方位、3-4-5 三角形），不回声实现公式。
    /// </summary>
    public class VectorArrowMathTests
    {
        const float k_PosTol = 1e-4f;
        static readonly Vector3 k_Origin = new Vector3(14f, 2f, -6f); // 任意 y ≠ 0 起点（y 直通）

        // ── 速度箭头长度 ─────────────────────────────────────────────────────────────
        [Test]
        public void VelocityLength_ZeroSpeed_ShowsReadableStub()
        {
            Assert.That(VectorArrowMath.VelocityArrowLengthM(0f), Is.GreaterThan(1f).And.LessThan(3f),
                "零速保底 stub：可读但不冒充运动（documented idle 行为）");
        }

        [Test]
        public void VelocityLength_ProportionalToSpeed_TwoMetersPerMps()
        {
            float l5 = VectorArrowMath.VelocityArrowLengthM(5f);
            float l10 = VectorArrowMath.VelocityArrowLengthM(10f);
            Assert.That(l5, Is.EqualTo(10f).Within(k_PosTol), "5 m/s × 2 m/(m/s) = 10 m（比例因子 documented）");
            Assert.That(l10, Is.EqualTo(20f).Within(k_PosTol), "10 m/s = 双倍长度（线性 ∝）");
            Assert.That(l10, Is.EqualTo(2f * l5).Within(k_PosTol), "长度比值 = 速度比值");
        }

        // ── 速度箭头端点（沿艏向）────────────────────────────────────────────────────
        [Test]
        public void VelocityTip_HeadingNorth_TipDueNorth()
        {
            var tip = VectorArrowMath.VelocityArrowTip(k_Origin, 0f, 5f);
            Assert.That(tip.x, Is.EqualTo(k_Origin.x).Within(k_PosTol), "朝北箭头不动 x");
            Assert.That(tip.z, Is.EqualTo(k_Origin.z + 10f).Within(k_PosTol), "5 m/s → 北向 10 m 端点");
            Assert.That(tip.y, Is.EqualTo(k_Origin.y).Within(k_PosTol), "箭头水平（y 直通）");
        }

        [Test]
        public void VelocityTip_HeadingEast_TipDueEast()
        {
            var tip = VectorArrowMath.VelocityArrowTip(k_Origin, 90f, 4f);
            Assert.That(tip.x, Is.EqualTo(k_Origin.x + 8f).Within(k_PosTol), "朝东 4 m/s → 东向 8 m 端点");
            Assert.That(tip.z, Is.EqualTo(k_Origin.z).Within(k_PosTol), "朝东箭头不动 z");
        }

        // ── 航点箭头端点（定长指活动航点）────────────────────────────────────────────
        [Test]
        public void WaypointTip_FarWaypointNorth_FixedLengthTowardIt()
        {
            var tip = VectorArrowMath.WaypointArrowTip(k_Origin, new Vector2(k_Origin.x, k_Origin.z + 100f), 0f);
            Assert.That(tip.x, Is.EqualTo(k_Origin.x).Within(k_PosTol));
            Assert.That(tip.z, Is.EqualTo(k_Origin.z + 10f).Within(k_PosTol), "正北 100 m 外航点 → 定长 10 m 北向指针");
        }

        [Test]
        public void WaypointTip_DistantWaypointBears3070_FixedLengthAlongBearing()
        {
            // 30/70 偏移 = 3-7 比例方位（模长 √58 ≠ 轴对齐）：端点 = 单位方位 × 10。
            // 断言逐分量 + 容差（整向量 Is.EqualTo+Within 走精确相等，浮点结合序差异会误报）。
            var wp = new Vector2(k_Origin.x + 30f, k_Origin.z + 70f);
            var tip = VectorArrowMath.WaypointArrowTip(k_Origin, wp, 0f);
            float dist = Vector2.Distance(new Vector2(k_Origin.x, k_Origin.z), wp);
            float len = VectorArrowMath.WaypointArrowLengthM;
            Assert.That(tip.x, Is.EqualTo(k_Origin.x + 30f / dist * len).Within(1e-3f), "x 沿方位分量");
            Assert.That(tip.z, Is.EqualTo(k_Origin.z + 70f / dist * len).Within(1e-3f), "z 沿方位分量");
            Assert.That(tip.y, Is.EqualTo(k_Origin.y).Within(k_PosTol), "水平指针（y 直通）");
            Assert.That(Vector3.Distance(k_Origin, tip), Is.EqualTo(10f).Within(1e-3f), "指针长度恒 10 m");
        }

        [Test]
        public void WaypointTip_OriginOnWaypoint_FallsBackToHeading()
        {
            var tip = VectorArrowMath.WaypointArrowTip(k_Origin, new Vector2(k_Origin.x, k_Origin.z), 90f);
            Assert.That(tip.x, Is.EqualTo(k_Origin.x + 10f).Within(k_PosTol), "零距退化回退艏向（90° = 东）");
            Assert.That(tip.z, Is.EqualTo(k_Origin.z).Within(k_PosTol));
        }
    }
}
