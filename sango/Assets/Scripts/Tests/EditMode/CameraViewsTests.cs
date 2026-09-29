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

        // ── Bridge 随船解算（M6 海峡 review S1 2026-09-29：船远离原点时固定机位首帧拍空海）──

        // 纯几何视锥投影（Camera.WorldToViewportPoint 等价口径，无 Camera 引擎对象）：
        // 旋转与 CameraRig.ApplyPose 同构（pitch 取负进 Euler）；d>0 = 相机前方（viewport z>0，
        // 修复前 census boatNDC z=-4959 = 正后方即 d<0）；|ndcX|,|ndcY|<1 = 在半 FOV 锥内
        // （x 侧按 aspect=1 最严口径：实际宽屏 aspect>1 只会更靠内）。
        static (float d, float ndcX, float ndcY) ProjectToCamera(CameraPose cam, Vector3 worldPoint)
        {
            var rot = Quaternion.Euler(-cam.PitchDeg, cam.YawDeg, 0f);
            var toPoint = worldPoint - cam.Position;
            float d = Vector3.Dot(toPoint, rot * Vector3.forward);
            float tanHalf = Mathf.Tan(cam.FieldOfView * 0.5f * Mathf.Deg2Rad);
            return (d,
                Vector3.Dot(toPoint, rot * Vector3.right) / (d * tanHalf),
                Vector3.Dot(toPoint, rot * Vector3.up) / (d * tanHalf));
        }

        [Test]
        public void Bridge_ShipRelative_OffsetRotatesWithHeadingAndLooksAlongIt()
        {
            var p = CameraViews.Resolve(CameraView.Bridge, k_Ship, 134f, bridgeShipRelative: true);
            float sin = Mathf.Sin(134f * Mathf.Deg2Rad), cos = Mathf.Cos(134f * Mathf.Deg2Rad);
            Assert.That(p.Position.x, Is.EqualTo(k_Ship.x - 40f * sin).Within(k_PosTol), "艉后 40 m = 沿艏向反方向（船体系 (0,12,-40) 随艏向旋转）");
            Assert.That(p.Position.z, Is.EqualTo(k_Ship.z - 40f * cos).Within(k_PosTol));
            Assert.That(p.Position.y, Is.EqualTo(12f).Within(k_PosTol), "桥楼高 12 m（与 M1 固定机位同高）");
            Assert.That(p.YawDeg, Is.EqualTo(134f).Within(k_AngleTolDeg), "视线沿艏向");
            Assert.That(p.PitchDeg, Is.EqualTo(-0.52f).Within(0.01f), "微俯沿用固定机位");
            Assert.That(p.FollowsShip, Is.True, "随船每帧重解（G 航行中船不出画面）");
            Assert.That(p.FieldOfView, Is.EqualTo(60f).Within(k_PosTol));
        }

        [Test]
        public void Bridge_ShipRelative_M6HeroBerth_ShipInsideFrustumFirstFrame()
        {
            // M6 主角泊位字面量（M6StraitSceneBootstrapper.k_HeroBerth/k_HeroHeadingDeg 同源）。
            var ship = new Vector3(-1500f, 0f, -5000f);
            var p = CameraViews.Resolve(CameraView.Bridge, ship, 134f, bridgeShipRelative: true);
            var (d, ndcX, ndcY) = ProjectToCamera(p, ship);
            Assert.That(d, Is.GreaterThan(0f), "船在相机前方（修复前固定机位 census boatNDC z=-4959）");
            Assert.That(ndcX, Is.InRange(-1f, 1f), "NDC x ∈ (-1,1)（aspect=1 最严口径；艏向系横向居中 ≈0）");
            Assert.That(ndcY, Is.InRange(-1f, 1f), "NDC y ∈ (-1,1)（12 m 高 / 40 m 前距 / 半 FOV 30° → ≈-0.5）");
        }

        [Test]
        public void Bridge_Fixed_M6HeroBerth_ShipBehindCamera_DocumentsRootCause()
        {
            // 反例钉根因：bridgeShipRelative=false（M1 语义零变化）时 M6 泊位船在固定机位
            // (0,12,-40) 望北的正后方——Player.log census boatNDC z=-4959 逐字对应（d≈-4960）。
            var ship = new Vector3(-1500f, 0f, -5000f);
            var p = CameraViews.Resolve(CameraView.Bridge, ship, 134f, bridgeShipRelative: false);
            var (d, _, _) = ProjectToCamera(p, ship);
            Assert.That(d, Is.LessThan(0f), "船在固定机位后方 5 km = 启动首帧无船的根因位");
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
