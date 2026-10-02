using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P2-S4 camera_free 自由位姿 EditMode 测试（twin-bridge-v1.md §8 演进记录；分屏联动 spike，
    /// 单向 Cesium 主→Twin 从，默认关）。CameraRig 在 Assembly-CSharp（Runtime 根无 asmdef），
    /// 经反射驱动（WakeFoamRigSmokeTests 先例）；CameraView 词汇在 Sango.Vessels 直接引用。
    /// 数值锚（独立算术，非回声实现）：**pitch 负=俯**（CameraPose 语义沿用）→ Unity
    /// Euler.x = −pitch（俯视 forward.y = −sin(|pitch|)）；yaw = 北向东顺时针（场景 +z 北/+x 东）。
    /// </summary>
    public class CameraRigFreePoseTests
    {
        GameObject _go;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("free-pose-cam");
            _go.AddComponent<Camera>(); // CameraRig.SetFreePose 缺 controlledCamera 时同对象自愈
        }

        [TearDown]
        public void TearDown()
        {
            if (_go != null) Object.DestroyImmediate(_go);
        }

        Component AddRig() => _go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.CameraRig"));

        static void Invoke(object obj, string method, params object[] args)
            => obj.GetType().GetMethod(method).Invoke(obj, args);

        static void InvokePrivate(object obj, string method)
            => obj.GetType().GetMethod(method,
                   System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .Invoke(obj, null);

        static bool FreePoseActive(object rig)
            => (bool)rig.GetType().GetProperty("FreePoseActive").GetValue(rig);

        [Test]
        public void SetFreePose_AppliesImmediately_WithCameraPoseSemantics()
        {
            var rig = AddRig();
            Invoke(rig, "SetFreePose", new Vector3(10f, 25f, 40f), 90f, -35f, 55f);

            Assert.That(FreePoseActive(rig), Is.True);
            var cam = _go.GetComponent<Camera>();
            Assert.That(cam.transform.position, Is.EqualTo(new Vector3(10f, 25f, 40f)));
            Assert.That(cam.transform.rotation.eulerAngles.x, Is.EqualTo(35f).Within(1e-3f),
                "pitch −35（俯）→ Unity Euler.x = +35（正 x = 俯，ApplyPose 同一取负约定）");
            Assert.That(cam.transform.rotation.eulerAngles.y, Is.EqualTo(90f).Within(1e-3f),
                "yaw 北向东顺时针（场景 +z 北/+x 东，TwinPose 同向）");
            Assert.That(cam.fieldOfView, Is.EqualTo(55f).Within(1e-4f));

            var forward = cam.transform.rotation * Vector3.forward;
            Assert.That(forward.y, Is.EqualTo(-Mathf.Sin(35f * Mathf.Deg2Rad)).Within(1e-4f),
                "pitch 负=俯：前向朝下（俯角 35°）");
            Assert.That(forward.x, Is.EqualTo(Mathf.Cos(35f * Mathf.Deg2Rad)).Within(1e-4f),
                "yaw 90° = 望东");
        }

        [Test]
        public void LateUpdate_HoldsFreePoseAgainstPresetResolution()
        {
            var rig = AddRig();
            Invoke(rig, "SetFreePose", new Vector3(1f, 2f, 3f), 45f, -80f, 60f);
            var cam = _go.GetComponent<Camera>();
            cam.transform.position = new Vector3(999f, 0f, 999f); // 模拟预设解算覆写

            InvokePrivate(rig, "LateUpdate");

            Assert.That(cam.transform.position, Is.EqualTo(new Vector3(1f, 2f, 3f)),
                "自由位姿生效期 LateUpdate 持续保持（离散联动事件，不回退预设解算）");
            Assert.That(cam.fieldOfView, Is.EqualTo(60f).Within(1e-4f));
        }

        [Test]
        public void SetView_PresetMessage_TakesControlBack()
        {
            var rig = AddRig();
            Invoke(rig, "SetFreePose", Vector3.zero, 0f, -30f, 60f);
            Assert.That(FreePoseActive(rig), Is.True);

            Invoke(rig, "SetView", CameraView.Chase); // camera 预设消息 = TwinBridgeService.HandleCamera 路径

            Assert.That(FreePoseActive(rig), Is.False, "预设消息收回控制权（联动 spike 单向语义退出缝）");
        }
    }
}
