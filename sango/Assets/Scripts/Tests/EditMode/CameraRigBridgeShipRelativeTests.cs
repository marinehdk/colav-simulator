using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M6 review S1（2026-09-29）引擎缝测试：CameraRig.SnapNow（Awake→SnapNow 即启动首帧
    /// 位姿写入路径）在 bridgeShipRelative=true/false 两态下的真实相机位姿与
    /// Camera.WorldToViewportPoint 船可见性。CameraRig 在 Assembly-CSharp（无 asmdef 覆盖，
    /// 测试 asmdef 不引用预定义程序集），故经反射驱动（WeatherFogOverrideTests 同款）；
    /// EditMode 下 AddComponent 不跑 Awake，SnapNow（private）手动反射调用 = 精确单步。
    /// 场景字面量与 M6StraitSceneBootstrapper.k_HeroBerth/k_HeroHeadingDeg 同源。
    /// </summary>
    public class CameraRigBridgeShipRelativeTests
    {
        GameObject _shipGo, _camGo;

        [TearDown]
        public void TearDown()
        {
            if (_camGo != null) Object.DestroyImmediate(_camGo);
            if (_shipGo != null) Object.DestroyImmediate(_shipGo);
        }

        static System.Reflection.BindingFlags Inst = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;

        Component BuildRig(Vector3 shipPos, float shipYawDeg, bool? setFlag)
        {
            _shipGo = new GameObject("rig-test-ship");
            _shipGo.transform.position = shipPos;
            _shipGo.transform.eulerAngles = new Vector3(0f, shipYawDeg, 0f);

            _camGo = new GameObject("rig-test-camera", typeof(Camera));
            var rigType = TestReflection.FindAssemblyCSharpType("Sango.CameraRig");
            var rig = _camGo.AddComponent(rigType);
            rigType.GetField("controlledCamera").SetValue(rig, _camGo.GetComponent<Camera>());
            rigType.GetField("followShip").SetValue(rig, _shipGo.transform);
            rigType.GetField("transitionSeconds").SetValue(rig, 1f);
            if (setFlag.HasValue) rigType.GetField("bridgeShipRelative").SetValue(rig, setFlag.Value);
            return rig;
        }

        void SnapNow(Component rig)
        {
            rig.GetType().GetMethod("SnapNow", Inst).Invoke(rig, null);
        }

        [Test]
        public void SnapNow_ShipRelative_M6HeroBerth_ShipVisibleInViewport()
        {
            var rig = BuildRig(new Vector3(-1500f, 0f, -5000f), 134f, setFlag: true);
            SnapNow(rig);

            var cam = _camGo.GetComponent<Camera>();
            // 船体系 (0,12,-40) 随艏向 134°：期望位姿独立几何（sin/cos 134°）。
            float sin = Mathf.Sin(134f * Mathf.Deg2Rad), cos = Mathf.Cos(134f * Mathf.Deg2Rad);
            Assert.That(cam.transform.position.x, Is.EqualTo(-1500f - 40f * sin).Within(0.01f), "艉后 40 m 沿艏向反方向");
            Assert.That(cam.transform.position.y, Is.EqualTo(12f).Within(0.01f), "桥楼高 12 m");
            Assert.That(cam.transform.position.z, Is.EqualTo(-5000f - 40f * cos).Within(0.01f));
            Assert.That(cam.transform.rotation.eulerAngles.y, Is.EqualTo(134f).Within(0.01f), "视线沿艏向（ApplyPose 单点旋转构造）");

            var vp = cam.WorldToViewportPoint(_shipGo.transform.position);
            Assert.That(vp.z, Is.GreaterThan(0f), "船在相机前方（viewport z>0；修复前 census boatNDC z=-4959 = 正后方）");
            Assert.That(vp.x, Is.InRange(0f, 1f), "船在画面横向范围内");
            Assert.That(vp.y, Is.InRange(0f, 1f), "船在画面纵向范围内（启动首帧有船 = review S1 验收）");
        }

        [Test]
        public void SnapNow_DefaultFlagFalse_KeepsM1FixedBridgePose()
        {
            // 默认值（字段初始化器 false，不显式置位）：M1 语义零变化——固定位姿逐位复现。
            var rig = BuildRig(new Vector3(-1500f, 0f, -5000f), 134f, setFlag: null);
            var flagValue = (bool)rig.GetType().GetField("bridgeShipRelative").GetValue(rig);
            Assert.That(flagValue, Is.False, "bridgeShipRelative 默认 false（M1 场景不序列化该字段时行为不变）");
            SnapNow(rig);

            var cam = _camGo.GetComponent<Camera>();
            Assert.That(cam.transform.position, Is.EqualTo(new Vector3(0f, 12f, -40f)).Within(0.01f), "M1 固定机位 (0,12,-40)");
            Assert.That(cam.transform.rotation.eulerAngles.y, Is.EqualTo(0f).Within(0.01f), "望北");
            Assert.That(cam.fieldOfView, Is.EqualTo(60f).Within(0.01f), "基准 FOV 60");
        }
    }
}
