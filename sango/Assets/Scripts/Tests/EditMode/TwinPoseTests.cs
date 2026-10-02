using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P2-S1 锚定与位姿映射测试（spec #89；纯函数）。
    /// 坐标约定（PHASE1-PLAN 冻结、CameraViews.cs 同源）：east→+x、north→+z、
    /// 艏向 (sin h, 0, cos h)、rotation.y = +psi·Rad2Deg。
    /// **psi=90° 断言**（PHASE1-PLAN 冻结首日验收动作，S0 发现 3 顺延到本段）：
    /// psi=π/2 → rotation.y=90°、艏向单位向量=+东。
    /// 锚定量级取 S0 真流事实（evidence/compact-v1-frames.jsonl：east≈39500、north≈6957500）。
    /// </summary>
    public class TwinPoseTests
    {
        const float Tolerance = 1e-4f;

        [Test]
        public void Psi90Degrees_Yaw90_HeadingEast()
        {
            float yaw = TwinPose.YawDegrees(Mathf.PI / 2f);
            Assert.That(yaw, Is.EqualTo(90f).Within(Tolerance), "rotation.y = +psi·Rad2Deg");
            var heading = TwinPose.HeadingVector(yaw);
            Assert.That(heading.x, Is.EqualTo(1f).Within(Tolerance), "艏向 = +东（+x）");
            Assert.That(heading.z, Is.EqualTo(0f).Within(Tolerance));
            Assert.That(heading.y, Is.EqualTo(0f).Within(Tolerance));
        }

        [Test]
        public void HeadingVector_ConventionNorthZeroEast90()
        {
            // Vector3+Within 走整体相等不逐分量容差——全部按分量断言（Psi90 同款）。
            var north = TwinPose.HeadingVector(0f);
            Assert.That(north.x, Is.EqualTo(0f).Within(Tolerance));
            Assert.That(north.z, Is.EqualTo(1f).Within(Tolerance));
            var east = TwinPose.HeadingVector(90f);
            Assert.That(east.x, Is.EqualTo(1f).Within(Tolerance), "90° = +东");
            Assert.That(east.z, Is.EqualTo(0f).Within(Tolerance));
            var west = TwinPose.HeadingVector(TwinPose.YawDegrees(-Mathf.PI / 2f)); // psi 域含负值
            Assert.That(west.x, Is.EqualTo(-1f).Within(Tolerance), "-90° = 西");
            Assert.That(west.z, Is.EqualTo(0f).Within(Tolerance));
        }

        [Test]
        public void Anchor_SubtractsGlobalUtmMagnitudes()
        {
            // S0 真流量级：本船 east≈39500、north≈6957500（UTM 域全域大数）。
            var anchor = TwinAnchor.FromShip(new ColavTelemetry.ShipEntry { east = 39500f, north = 6957500f });
            var local = anchor.ToLocal(39510.5, 6957520.25);
            Assert.That(local.x, Is.EqualTo(10.5f).Within(Tolerance), "east − 锚 = 局部东");
            Assert.That(local.y, Is.EqualTo(20.25f).Within(Tolerance), "north − 锚 = 局部北");

            var fromOrigin = TwinAnchor.FromOrigin(37000.0, 6955000.0); // replay context enc.origin_* 形状
            var local2 = fromOrigin.ToLocal(37100.0, 6955100.0);
            Assert.That(local2, Is.EqualTo(new Vector2(100f, 100f)).Within(Tolerance));
        }

        [Test]
        public void ScenePosition_EastToX_NorthToZ()
        {
            var anchor = TwinAnchor.FromShip(new ColavTelemetry.ShipEntry { east = 39500f, north = 6957500f });
            var position = TwinPose.ScenePosition(
                new ColavTelemetry.ShipEntry { east = 39600f, north = 6957400f }, anchor);
            Assert.That(position, Is.EqualTo(new Vector3(100f, 0f, -100f)).Within(Tolerance));
        }

        [Test]
        public void FirstFrameOwnship_AnchorsToZero()
        {
            // 首帧本船锚定后自身在原点（对遇场景 target 由 delta 决定，规格 §实现内容 2）。
            var own = new ColavTelemetry.ShipEntry { id = 0, east = 39500f, north = 6957500f, psi = 0.7853982f };
            var anchor = TwinAnchor.FromShip(own);
            Assert.That(TwinPose.ScenePosition(own, anchor), Is.EqualTo(Vector3.zero).Within(Tolerance));
            var target = new ColavTelemetry.ShipEntry { id = 1, east = 41500f, north = 6959500f };
            Assert.That(TwinPose.ScenePosition(target, anchor), Is.EqualTo(new Vector3(2000f, 0f, 2000f)).Within(0.5f));
        }

        [Test]
        public void LerpEntries_LinearBetweenFrames()
        {
            var a = new ColavTelemetry.ShipEntry { id = 0, east = 0f, north = 0f, psi = 0f, sog = 0f, u = 0f, length = 8.45f, width = 2.71f };
            var b = new ColavTelemetry.ShipEntry { id = 0, east = 10f, north = 20f, psi = Mathf.PI / 2f, sog = 7f, u = 7f, length = 8.45f, width = 2.71f, active = true };
            var mid = TwinPose.LerpEntries(a, b, 0.5f);
            Assert.That(mid.east, Is.EqualTo(5f).Within(Tolerance));
            Assert.That(mid.north, Is.EqualTo(10f).Within(Tolerance));
            Assert.That(mid.psi, Is.EqualTo(Mathf.PI / 4f).Within(Tolerance), "艏向随帧线性插值");
            Assert.That(mid.sog, Is.EqualTo(3.5f).Within(Tolerance));
            Assert.That(mid.active, Is.True, "静态/权威量取新帧");
            // alpha 越界钳位 = 不外推（spec #89）。
            var clamped = TwinPose.LerpEntries(a, b, 1.7f);
            Assert.That(clamped.east, Is.EqualTo(10f).Within(Tolerance));
        }

        [Test]
        public void LerpEntries_PsiShortestPathWrap()
        {
            // 对遇 ψ=-3π/4 → +3π/4：短弧经 ±π（180°），LerpAngle 度制防回绕跳变。
            var a = new ColavTelemetry.ShipEntry { psi = -3f * Mathf.PI / 4f };
            var b = new ColavTelemetry.ShipEntry { psi = 3f * Mathf.PI / 4f };
            var mid = TwinPose.LerpEntries(a, b, 0.5f);
            Assert.That(Mathf.Abs(Mathf.DeltaAngle(mid.psi * Mathf.Rad2Deg, 180f)), Is.LessThan(0.01f));
        }

        [Test]
        public void InterpolationAlpha_ClampsAndDegenerates()
        {
            Assert.That(TwinPose.InterpolationAlpha(0.25, 0.0, 0.5), Is.EqualTo(0.5f).Within(Tolerance));
            Assert.That(TwinPose.InterpolationAlpha(-1.0, 0.0, 0.5), Is.EqualTo(0f).Within(Tolerance), "早于前帧钳 0");
            Assert.That(TwinPose.InterpolationAlpha(9.0, 0.0, 0.5), Is.EqualTo(1f).Within(Tolerance), "超前最新帧钳 1（不外推）");
            Assert.That(TwinPose.InterpolationAlpha(0.0, 0.5, 0.5), Is.EqualTo(1f).Within(Tolerance), "零帧距退化吸最新");
        }
    }

    /// <summary>
    /// P2-S1 TwinShipFactory 选型测试（spec #89）：truth.length → 编目最近实测 LOA，
    /// 平手取先、无匹配返回 null（调用方跳过并计数，不脑补）。
    /// </summary>
    public class TwinShipFactoryTests
    {
        static VesselCatalog Catalog(params (VesselClass cls, float loa)[] entries)
        {
            var catalog = ScriptableObject.CreateInstance<VesselCatalog>();
            catalog.entries = new VesselCatalog.Entry[entries.Length];
            for (int i = 0; i < entries.Length; i++)
                catalog.entries[i] = new VesselCatalog.Entry { vesselClass = entries[i].cls, loaMeters = entries[i].loa };
            return catalog;
        }

        [Test]
        public void SelectsNearestLoa()
        {
            var catalog = Catalog((VesselClass.Small, 12f), (VesselClass.Fcb45, 45f), (VesselClass.Tanker, 300f));
            Assert.That(TwinShipFactory.Select(catalog, 8.45f).vesselClass, Is.EqualTo(VesselClass.Small), "head_on 本船 8.45m");
            Assert.That(TwinShipFactory.Select(catalog, 44.1f).vesselClass, Is.EqualTo(VesselClass.Fcb45), "replay run 745d63fd 本船 44.1m");
            Assert.That(TwinShipFactory.Select(catalog, 299f).vesselClass, Is.EqualTo(VesselClass.Tanker));
        }

        [Test]
        public void NullOrEmptyCatalog_ReturnsNull()
        {
            Assert.That(TwinShipFactory.Select(null, 10f), Is.Null);
            var catalog = Catalog();
            Assert.That(TwinShipFactory.Select(catalog, 10f), Is.Null, "空编目不脑补替身");
        }
    }
}
