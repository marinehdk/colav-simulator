using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-E2 相机视图位姿缝 EditMode 测试（spec #85 Testing Decisions）。只打纯解析器
    /// CameraViews.Resolve/Next，无 Camera/Transform 引擎调用（船位姿作参数）。
    /// 钉死的坐标约定（WaypointKinematicsTests 同源）：东 = +x，北 = +z，艏向角自北顺时针，
    /// 艏向单位向量 = (sin h, 0, cos h)。期望值全部来自 spec 的独立几何事实
    /// （桥楼 = M1 机位 FOV 60；bow 在艏部上空；chase 艉后上方；top-down 船正上方 160 m
    /// 透视战术档北向上 FOV 35），不回声实现里的常量算式。
    /// </summary>
    public class CameraViewsTests
    {
        const float k_PosTol = 1e-3f;
        const float k_AngleTolDeg = 0.01f;

        static readonly Vector3 k_Ship = new Vector3(100f, 0f, 50f);

        // ── Bridge：固定机位，与船位姿无关 ──────────────────────────────────────────
        [Test]
        public void Bridge_FixedPose_IgnoringShipPose()
        {
            var a = CameraViews.Resolve(CameraView.Bridge, new Vector3(0f, 0f, 0f), 0f);
            var b = CameraViews.Resolve(CameraView.Bridge, k_Ship, 137f);
            Assert.That(b.Position, Is.EqualTo(a.Position), "桥楼机位不随船");
            Assert.That(b.Position, Is.EqualTo(new Vector3(0f, 12f, -40f)).Within(k_PosTol), "M1 既有桥楼位 (0,12,-40)");
            Assert.That(b.YawDeg, Is.EqualTo(0f).Within(k_AngleTolDeg), "望北（岛群中心在 +z）");
            Assert.That(b.PitchDeg, Is.EqualTo(-0.52f).Within(0.01f), "微俯（望 180 m 外 10 m 高目标）");
            Assert.That(b.FollowsShip, Is.False, "桥楼不跟随");
            Assert.That(b.FieldOfView, Is.EqualTo(60f).Within(k_PosTol), "桥楼透视 FOV 60（= M1 场景相机，渲染零变化）");
        }

        // ── Bow：艏部上空、艏向前方（船体系偏移随艏向旋转）─────────────────────────
        [Test]
        public void Bow_HeadingNorth_SitsAheadOfShipLookingForward()
        {
            var p = CameraViews.Resolve(CameraView.Bow, k_Ship, 0f);
            Assert.That(p.Position.x, Is.EqualTo(100f).Within(k_PosTol), "朝北时艏向前 8 m 不动 x");
            Assert.That(p.Position.z, Is.EqualTo(58f).Within(k_PosTol), "朝北时艏向前 8 m = z + 8");
            Assert.That(p.Position.y, Is.EqualTo(4.5f).Within(k_PosTol), "艏部上空 4.5 m");
            Assert.That(p.YawDeg, Is.EqualTo(0f).Within(k_AngleTolDeg), "沿艏向前看");
            Assert.That(p.FollowsShip, Is.True, "bow 随船（Autonomous 下船在走）");
            Assert.That(p.FieldOfView, Is.EqualTo(60f).Within(k_PosTol), "常规档透视 FOV 60");
        }

        [Test]
        public void Bow_HeadingEast_OffsetRotatesWithShip()
        {
            var p = CameraViews.Resolve(CameraView.Bow, k_Ship, 90f);
            Assert.That(p.Position.x, Is.EqualTo(108f).Within(k_PosTol), "朝东时艏向前 8 m = x + 8（船体系偏移随艏向转）");
            Assert.That(p.Position.z, Is.EqualTo(50f).Within(k_PosTol), "朝东时 z 不动");
            Assert.That(p.YawDeg, Is.EqualTo(90f).Within(k_AngleTolDeg), "视线随艏向转东");
        }

        // ── Chase：艉后上方望船（艉后 = 艏向反方向）─────────────────────────────────
        [Test]
        public void Chase_HeadingNorth_HoversAsternAbove()
        {
            var p = CameraViews.Resolve(CameraView.Chase, k_Ship, 0f);
            Assert.That(p.Position, Is.EqualTo(new Vector3(100f, 18f, 20f)).Within(k_PosTol), "艉后 30 m（z − 30）高 18 m");
            Assert.That(p.YawDeg, Is.EqualTo(0f).Within(k_AngleTolDeg), "望向船 = 沿艏向方向");
            Assert.That(p.PitchDeg, Is.EqualTo(-26.6f).Within(0.05f), "从 18 m 高俯视 30 m 外的船");
            Assert.That(p.FollowsShip, Is.True);
        }

        [Test]
        public void Chase_HeadingSouth_AsternFlipsToNorth()
        {
            var p = CameraViews.Resolve(CameraView.Chase, k_Ship, 180f);
            Assert.That(p.Position.z, Is.EqualTo(80f).Within(k_PosTol), "朝南船的艉后 = 世界 +z 方向（z + 30）");
            Assert.That(p.YawDeg, Is.EqualTo(180f).Within(k_AngleTolDeg), "视线朝南（与船同向望船）");
        }

        // ── TopDown：船正上方、透视战术档、北向上（验收修正 2 轮：ortho 触发 HDRP 投影切换
        //    破坏管线渲染状态 → 全透视 160 m / pitch −80° / FOV 35°，船恒画面正中可辨）──
        [Test]
        public void TopDown_PerspectiveAboveShipNorthUp()
        {
            var p = CameraViews.Resolve(CameraView.TopDown, k_Ship, 0f);
            Assert.That(p.Position, Is.EqualTo(new Vector3(100f, 160f, 50f)).Within(k_PosTol), "船正上空 160 m（随船平移）");
            Assert.That(p.PitchDeg, Is.EqualTo(-80f).Within(k_AngleTolDeg), "俯 80°（视线略北倾，足迹中心偏北）");
            Assert.That(p.YawDeg, Is.EqualTo(0f).Within(k_AngleTolDeg), "北向上（海图方向约定，不随艏向）");
            Assert.That(p.FieldOfView, Is.EqualTo(35f).Within(k_PosTol), "俯视战术档透视 FOV 35°（地面足迹 ~100 m，小船 ~100+ px）");
            Assert.That(p.FollowsShip, Is.True);
        }

        // ── 循环顺序：C 键 Bridge → Bow → Chase → TopDown → Bridge ─────────────────
        [Test]
        public void Next_CyclesAllFourViewsInOrder()
        {
            Assert.That(CameraViews.Next(CameraView.Bridge), Is.EqualTo(CameraView.Bow));
            Assert.That(CameraViews.Next(CameraView.Bow), Is.EqualTo(CameraView.Chase));
            Assert.That(CameraViews.Next(CameraView.Chase), Is.EqualTo(CameraView.TopDown));
            Assert.That(CameraViews.Next(CameraView.TopDown), Is.EqualTo(CameraView.Bridge), "循环回桥楼");
        }
    }
}
