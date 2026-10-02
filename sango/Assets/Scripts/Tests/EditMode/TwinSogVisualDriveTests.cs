using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P2-S4 D 收口 EditMode 数值测试：Twin 槽位 sog → 速度矢量长度 + 尾迹强度
    /// （spec #89 S1 留尾；类头注遗留收口，Demo 路径零变化）。
    /// VectorArrows/WakeFoamRig/WakeFoamCore 在 Assembly-CSharp（Runtime 根无 asmdef），经反射驱动
    /// （WakeFoamRigSmokeTests 先例）；VectorArrowMath 在 Sango.Vessels 直接引用做端点对拍——
    /// 期望值独立算术（2 m/(m/s)、零速 stub），不回声实现。
    /// </summary>
    public class TwinSogVisualDriveTests
    {
        GameObject _ship;

        [SetUp]
        public void SetUp()
        {
            _ship = new GameObject("twin-sog-ship");
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Object.DestroyImmediate(cube.GetComponent<Collider>());
            cube.transform.SetParent(_ship.transform, false);
            cube.transform.localPosition = new Vector3(0f, 0.5f, 0f);
            cube.transform.localScale = new Vector3(2f, 1f, 4f); // 包围盒可建 rig（WakeFoamRig 需 MeshFilter）
        }

        [TearDown]
        public void TearDown()
        {
            M8Quality.SetTier(M8QualityTier.High); // 复原静态记账（防跨测试泄漏）
            if (_ship != null) Object.DestroyImmediate(_ship);
        }

        Component AddArrows(System.Func<float> sogSource, System.Func<bool> active = null, float bowYawOffset = 0f)
        {
            var arrows = _ship.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.VectorArrows"));
            var type = arrows.GetType();
            // EditMode AddComponent 不触发 OnEnable（WakeFoamRigSmokeTests 同坑）：显式建 rig。
            type.GetMethod("OnEnable",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance).Invoke(arrows, null);
            type.GetField("twinSpeedMps").SetValue(arrows, sogSource);
            type.GetField("twinActive").SetValue(arrows, active ?? (System.Func<bool>)(() => true));
            type.GetField("twinBowYawOffsetDeg").SetValue(arrows, bowYawOffset);
            return arrows;
        }

        static void Tick(Component arrows, bool twinDriven)
            => arrows.GetType().GetMethod("Tick").Invoke(arrows, new object[] { twinDriven });

        static Transform Rig(Component arrows)
            => (Transform)arrows.GetType().GetField("m_Root",
                   System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .GetValue(arrows); // rig 为世界空间根（非船子物体，类头注）——从字段取，不 Find 船树

        static Transform Child(Component arrows, string path)
            => path.Length == 0 ? Rig(arrows) : Rig(arrows).Find(path);

        // ── VectorArrows：Twin sog → 速度矢量 ───────────────────────────────────

        [Test]
        public void TwinSog_DrivesVelocityArrowLengthAndHeading()
        {
            _ship.transform.rotation = Quaternion.Euler(0f, 90f, 0f); // 艏东（psi=90，补偿 0）
            float sog = 3f;
            var arrows = AddArrows(() => sog);
            Tick(arrows, true);

            var root = Child(arrows, "");
            Assert.That(root.gameObject.activeSelf, Is.True, "Twin 活动态 → 矢量树显");
            var arrow = Child(arrows, "VelocityArrow");
            Assert.That(arrow.position, Is.EqualTo(_ship.transform.position + Vector3.up * 3f).Within(1e-3f),
                "箭头 origin = 船 + 甲板高 3 m");

            float expectedLength = VectorArrowMath.VelocityMetersPerMps * 3f; // 独立算术 2×3 = 6 m
            var shaft = Child(arrows, "VelocityArrow/Velocity.Shaft");
            Assert.That(shaft.localScale.z, Is.EqualTo(expectedLength - 1.5f).Within(1e-3f),
                "杆长 = 总长 − 头长 1.5（LayoutArrow 同式）");
            var headDir = (Child(arrows, "VelocityArrow/Velocity.Head").position - arrow.position).normalized;
            Assert.That(headDir.x, Is.EqualTo(1f).Within(1e-3f), "指向 = 艏向东");

            // sog 变化 → 长度跟随（收口语义核心断言）
            sog = 1f;
            Tick(arrows, true);
            Assert.That(shaft.localScale.z, Is.EqualTo(VectorArrowMath.VelocityMetersPerMps - 1.5f).Within(1e-3f),
                "sog 1 m/s → 总长 2 m");
        }

        [Test]
        public void TwinSog_Zero_KeepsStubArrow()
        {
            var arrows = AddArrows(() => 0f);
            Tick(arrows, true);
            var shaft = Child(arrows, "VelocityArrow/Velocity.Shaft");
            float stubShaft = VectorArrowMath.VelocityStubLengthM - 1.5f;
            Assert.That(shaft.localScale.z, Is.EqualTo(Mathf.Max(0.05f, stubShaft)).Within(1e-4f),
                "零速 stub：总长钳 stub 1.5 m，杆 = 总长 − 头长");
        }

        [Test]
        public void TwinMode_HidesWaypointArrow_AndDemoPathStaysDormant()
        {
            var arrows = AddArrows(() => 3f);
            Tick(arrows, true);
            Assert.That(Child(arrows, "WaypointArrow").gameObject.activeSelf, Is.False,
                "Twin 无航点表 → 航点箭头隐藏");

            Tick(arrows, false); // Demo 路径（无 follower：S1 语义原样 → 整树休眠）
            Assert.That(Child(arrows, "").gameObject.activeSelf, Is.False,
                "follower 缺失的 Demo 路径行为逐位不变");
        }

        [Test]
        public void TwinInactive_SleepsTree()
        {
            var arrows = AddArrows(() => 3f, () => false);
            Tick(arrows, true);
            Assert.That(Child(arrows, "").gameObject.activeSelf, Is.False,
                "twinActive=false（会话关闸/槽位不在位）→ 整树休眠");
        }

        // ── WakeFoamRig：Twin sog → 尾迹强度 ────────────────────────────────────

        [Test]
        public void TwinSog_DrivesWakeIntensity_SameCurveAsFollowerPath()
        {
            var rig = _ship.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.WakeFoamRig"));
            var type = rig.GetType();
            type.GetField("loaMeters").SetValue(rig, 12f);
            type.GetMethod("BuildRig",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance).Invoke(rig, null);
            M8Quality.SetTier(M8QualityTier.High);

            // follower 路径基准：同速度下两条路径必须同值（接线只是换源，曲线零改动）
            type.GetMethod("ApplySpeed").Invoke(rig, new object[] { 2.5f });
            float followerBaseline = (float)type.GetProperty("LastWakeIntensity01").GetValue(rig);
            Assert.That(followerBaseline, Is.GreaterThan(0f), "2.5 m/s 在爬坡段有强度");

            float sog = 2.5f;
            type.GetField("twinSpeedMps").SetValue(rig, (System.Func<float>)(() => sog));
            type.GetMethod("LateUpdate",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance).Invoke(rig, null);
            Assert.That((float)type.GetProperty("LastWakeIntensity01").GetValue(rig),
                Is.EqualTo(followerBaseline).Within(1e-5f), "Twin sog 源与 follower 源同一强度曲线");

            sog = 0f;
            type.GetMethod("LateUpdate",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance).Invoke(rig, null);
            Assert.That((float)type.GetProperty("LastWakeIntensity01").GetValue(rig), Is.EqualTo(0f), "零 sog 零强度");
            Assert.That((float)type.GetProperty("LastSprayRatePerSide").GetValue(rig), Is.EqualTo(0f), "零 sog 零发射");
        }
    }
}
